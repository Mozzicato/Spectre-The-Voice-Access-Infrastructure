"""The case compiler: transcript -> structured institutional case.

Pipeline:
    transcript -> domain classification -> schema-guided extraction
               -> missing-field detection -> routing -> case packet

The engine is domain-agnostic. Everything domain-specific lives in `schemas.py`.

Two rules the extraction prompt enforces, both of them safety requirements rather than
quality preferences:

1. Nothing is invented. A detail not present in the transcript stays null and is listed
   in `missing_information`. An institutional case built on a hallucinated amount or
   agency is worse than no case at all.
2. The output records what the SPEAKER REPORTED, never a legal or factual finding.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app import llm, schemas
from app.normalize import (
    normalize_loose,
    spoken_digit_strings,
    spoken_numbers_to_values,
)

SYSTEM_PROMPT = """\
You convert a spoken account, transcribed from natural African code-switched speech \
(Nigerian Pidgin, Yoruba-English, Igbo-English, Hausa-English), into a structured \
institutional case record.

Absolute rules:
1. NEVER invent information. If a detail is not in the transcript, use null (or an empty \
list) and name that field in `missing_information`.
2. Record only what the SPEAKER REPORTED. Do not make legal or factual determinations. \
Write "reported that the landlord asked them to leave", never "was illegally evicted".
3. Keep the speaker's own meaning. Do not sanitise Pidgin or Yoruba into different claims.
4. Preserve numbers exactly as meant: "forty-five thousand" is 45000, not 4500. A \
reference number read out digit by digit is joined with no spaces.
5. NEGATION IS CRITICAL. "He never paid me" and "he paid me" are opposite cases. If the \
transcript is garbled around a negation, lower `confidence` and say so in \
`missing_information`.
6. Relative time references ("yesterday", "last month", "since March") are valid \nvalues - record them exactly as spoken rather than leaving the field null.
7. The transcript comes from an imperfect speech model. If something looks like a \
mis-transcription, do not silently fix it into a confident claim - mark low confidence.

Return only the structured record."""

CLASSIFY_PROMPT = """\
Classify which institution should handle this spoken account.

Answer with JSON: {"domain": "legal" | "financial" | "public_service", \
"reason": "<short reason>"}

legal          - tenancy, employment, consumer, land, family disputes
financial      - banks, transfers, cards, ATMs, loans, payments
public_service - roads, water, electricity supply, streetlights, waste, government \
facilities

Transcript:
---
{transcript}
---"""


@dataclass
class CompiledCase:
    domain: str
    case_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    route: str = ""
    route_label: str = ""
    confidence: str = "medium"
    transcript: str = ""
    extractor: str = ""
    latency_s: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @property
    def completeness(self) -> float:
        schema = schemas.get(self.domain)
        required = schema.required_fields
        if not required:
            return 1.0
        filled = sum(1 for name in required if _is_filled(self.fields.get(name)))
        return filled / len(required)


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"null", "none", "n/a"}
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


# --------------------------------------------------------------------------------------
# rule-based fallback (used when no LLM key is configured)
# --------------------------------------------------------------------------------------

_DOMAIN_CUES = {
    "financial": ["bank", "transfer", "account", "atm", "card", "naira", "debit",
                  "alert", "gtbank", "access", "zenith", "uba", "first bank", "loan",
                  "transaction", "reference", "withdraw", "reversal", "refund"],
    "public_service": ["streetlight", "street light", "road", "drainage", "water",
                       "electricity", "light", "waste", "refuse", "council",
                       "local government", "agency", "meter", "borehole", "clinic",
                       "health centre", "health center", "flood", "sanitation"],
    "legal": ["landlord", "tenant", "rent", "evict", "comot", "sack", "salary",
              "employer", "boss", "contract", "court", "lawyer", "notice", "quit",
              "deposit", "dismiss", "employment", "seller", "refund", "generator"],
}

_CASE_CUES = {
    "tenancy_dispute": ["landlord", "rent", "evict", "comot", "tenant", "deposit"],
    "employment_dispute": ["sack", "salary", "employer", "dismiss", "wages", "job"],
    "consumer_dispute": ["seller", "bought", "buy", "generator", "market", "contractor"],
    "failed_transfer": ["transfer", "never receive", "no enter", "not received"],
    "unauthorized_transaction": ["unauthorized", "not authorize", "without my",
                                 "fraud", "did not", "permission"],
    "failed_atm_withdrawal": ["atm", "machine", "dispense", "no comot", "withdraw"],
    "payment_dispute": ["order", "seller", "shipped", "online", "merchant"],
    "loan_dispute": ["loan", "repay", "deducted", "interest", "app"],
    "streetlight_failure": ["streetlight", "street light", "dark", "light for our street"],
    "road_or_drainage": ["road", "drainage", "flood", "pothole", "gutter"],
    "water_supply": ["water", "borehole", "jerrican", "tap"],
    "electricity_supply": ["electricity", "meter", "bill", "disco", "prepaid", "nepa"],
    "waste_management": ["waste", "refuse", "dirt", "sanitation", "pantı", "panti"],
    "health_facility": ["health", "clinic", "doctor", "hospital", "nurse"],
}


def _rule_domain(transcript: str) -> str:
    flat = normalize_loose(transcript)
    scores = {
        domain: sum(1 for cue in cues if cue in flat)
        for domain, cues in _DOMAIN_CUES.items()
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] else "legal"


def _rule_case_type(transcript: str, schema: schemas.Schema) -> str:
    flat = normalize_loose(transcript)
    best, best_score = None, 0
    for case_type in schema.case_types:
        score = sum(1 for cue in _CASE_CUES.get(case_type, []) if cue in flat)
        if score > best_score:
            best, best_score = case_type, score
    return best or schema.case_types[-1]


_DATE_RE = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|"
    r"august|september|october|november|december)|(?:january|february|march|april|may|june|"
    r"july|august|september|october|november|december)\s+\d{1,2}|yesterday|today|last week|"
    r"last month|last year|since \d{4}|\d{4})\b",
    re.IGNORECASE,
)


def _rule_extract(transcript: str, schema: schemas.Schema) -> dict:
    """Deterministic best-effort extraction, used only when no LLM key is available."""
    # A reference number is a long digit run; an amount is not. Without this split the
    # fallback reads "0987654321" as an amount of 987,654,321 and files the real amount
    # as the reference -- exactly backwards.
    refs = spoken_digit_strings(transcript)
    ref_candidates = [r for r in refs if len(r) >= 8]
    reference = max(ref_candidates, key=len) if ref_candidates else None
    ref_values = {int(r) for r in ref_candidates if r.isdigit()}

    amounts = [a for a in spoken_numbers_to_values(transcript) if a not in ref_values]
    dates = [m.group(0) for m in _DATE_RE.finditer(transcript)]

    out: dict[str, Any] = {}
    for f in schema.fields:
        if f.kind == "list":
            out[f.name] = []
        else:
            out[f.name] = None

    if "amounts" in out:
        out["amounts"] = [f"{a:,}" for a in amounts]
    if "amount" in out and amounts:
        out["amount"] = amounts[0]  # first mentioned is usually the principal
    if "dates" in out:
        out["dates"] = dates
    if "date" in out and dates:
        out["date"] = dates[0]
    if "transaction_reference" in out and reference:
        out["transaction_reference"] = reference
    if "problem" in out:
        sentence = re.split(r"[.!?]", transcript.strip())
        out["problem"] = (sentence[0].strip() if sentence else transcript.strip())[:220]
    return out


# --------------------------------------------------------------------------------------


class CaseCompiler:
    """Transcript in, structured case out. Same engine for every domain."""

    def __init__(self, client: "llm.LLMClient | None" = None, use_llm: bool | None = None):
        if use_llm is None:
            use_llm = llm.available()
        self.use_llm = use_llm
        # Every configured provider, in preference order. If the primary is rate-limited
        # or out of credit, the next key takes over instead of the whole run quietly
        # dropping to rule-based extraction and corrupting the benchmark.
        self._clients: list[llm.LLMClient] = []
        if client is not None:
            self._clients = [client]
        elif self.use_llm:
            self._clients = llm.all_clients()
        if not self._clients:
            self.use_llm = False
        self._active = self._clients[0] if self._clients else None

    @property
    def _client(self):
        return self._active

    def _call_json(self, system: str, user: str, schema: dict, max_tokens: int = 3000):
        """Try each provider in turn. Raises only if every one fails."""
        errors = []
        for candidate in self._clients:
            try:
                out = candidate.complete_json(system, user, schema, max_tokens)
                self._active = candidate
                return out
            except Exception as exc:
                errors.append(f"{candidate.label}: {type(exc).__name__}")
                continue
        raise RuntimeError("all LLM providers failed -> " + "; ".join(errors))

    @property
    def extractor_label(self) -> str:
        if self.use_llm and self._active:
            return self._active.label
        return "rule_based_fallback"

    def classify(self, transcript: str) -> str:
        if self.use_llm and self._clients:
            try:
                out = self._call_json(
                    "You are a precise classifier. Reply with JSON only.",
                    CLASSIFY_PROMPT.format(transcript=transcript),
                    {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string",
                                       "enum": ["legal", "financial", "public_service"]},
                            "reason": {"type": "string"},
                        },
                        "required": ["domain"],
                    },
                    max_tokens=200,
                )
                domain = str(out.get("domain", "")).lower()
                if domain in schemas.SCHEMAS:
                    return domain
            except Exception:
                pass
        return _rule_domain(transcript)

    def compile(self, transcript: str, domain: str | None = None) -> CompiledCase:
        started = time.monotonic()
        transcript = (transcript or "").strip()
        warnings: list[str] = []

        if not transcript:
            return CompiledCase(
                domain=domain or "legal", case_type="unknown",
                transcript="", extractor=self.extractor_label,
                warnings=["empty transcript - nothing to compile"],
                confidence="low",
            )

        resolved = (domain or self.classify(transcript)).lower()
        schema = schemas.get(resolved)

        extracted: dict[str, Any] = {}
        confidence = "medium"

        if self.use_llm and self._clients:
            try:
                extracted = self._call_json(
                    SYSTEM_PROMPT,
                    f"Domain: {schema.label}\n\nTranscript:\n---\n{transcript}\n---",
                    schema.json_schema(),
                )
                confidence = str(extracted.pop("confidence", "medium"))
            except Exception as exc:
                warnings.append(
                    f"LLM extraction failed ({type(exc).__name__}), fell back to rules"
                )
                extracted = {}

        if not extracted:
            extracted = _rule_extract(transcript, schema)
            extracted["case_type"] = _rule_case_type(transcript, schema)
            confidence = "low"
            reason = ("no LLM key configured" if not (self.use_llm and self._clients)
                      else "the configured LLM call failed")
            warnings.append(
                f"rule-based extraction ({reason}) - field accuracy is degraded"
            )

        case_type = str(extracted.pop("case_type", "") or
                        _rule_case_type(transcript, schema))
        if case_type not in schema.case_types:
            case_type = schema.case_types[-1]

        declared_missing = extracted.pop("missing_information", []) or []
        fields = {k: v for k, v in extracted.items()
                  if k in {f.name for f in schema.fields}}

        missing = detect_missing(fields, schema, declared_missing)
        route, route_label = schema.routes.get(
            case_type, ("general_triage", "General triage queue")
        )

        # Cross-check: a negation in the transcript that produced no claim is a red flag.
        from app.normalize import negation_markers
        if negation_markers(transcript) > 0 and not any(
            _is_filled(v) for k, v in fields.items() if k in {"problem", "events", "claims"}
        ):
            warnings.append(
                "transcript contains negation but no claim was extracted - review manually"
            )

        case = CompiledCase(
            domain=schema.key,
            case_type=case_type,
            fields=fields,
            missing_information=missing,
            route=route,
            route_label=route_label,
            confidence=confidence,
            transcript=transcript,
            extractor=self.extractor_label,
            latency_s=round(time.monotonic() - started, 3),
            warnings=warnings,
        )
        from app.questions import build_questions
        case.questions = build_questions(case, schema)
        return case


def detect_missing(fields: dict, schema: schemas.Schema,
                   declared: list[str] | None = None) -> list[str]:
    """Required fields that are empty. The model's own list is merged in, not trusted."""
    missing = [name for name in schema.required_fields if not _is_filled(fields.get(name))]
    # The model's own list is merged in, but only for fields the schema marks required.
    # Otherwise every unfilled optional field becomes a question the user should not be
    # asked, and "ask only what is necessary" stops being true.
    for name in declared or []:
        clean = str(name).strip()
        if clean and clean not in missing and clean in schema.required_fields:
            missing.append(clean)
    return missing
