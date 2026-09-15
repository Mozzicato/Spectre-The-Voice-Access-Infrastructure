"""Routing and case-packet generation.

Routing is deliberately rule-based, driven by the tables in `schemas.py`. An LLM is never
asked which agency handles a complaint, because a hallucinated agency name in an
institutional case file is worse than no routing at all.

What this produces is an actionable case packet and a recommended workflow. It does NOT
submit anything to any real government or bank system, and it says so.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app import config, schemas

if TYPE_CHECKING:
    from app.compiler import CompiledCase

# What a human reviewer should do next, per route.
NEXT_STEPS: dict[str, list[str]] = {
    "legal_aid_review": [
        "Assign to a legal aid officer for review",
        "Confirm the property/employment location and jurisdiction",
        "Request any documents listed as missing evidence",
    ],
    "labour_review": [
        "Assign to labour/employment desk",
        "Confirm employment start date and terms",
        "Request payslips or contract if available",
    ],
    "consumer_protection_review": [
        "Log as a consumer complaint against the named seller",
        "Request proof of purchase",
    ],
    "general_legal_triage": ["Route to a legal officer for manual triage"],
    "bank_dispute_workflow": [
        "Raise a formal dispute with the named bank",
        "Supply the transaction reference and date",
        "Track the reversal/refund timeline",
    ],
    "fraud_review": [
        "Escalate to the fraud desk as a suspected unauthorised transaction",
        "Advise the account holder to request a card/account block",
        "Preserve the transaction alerts as evidence",
    ],
    "merchant_dispute_workflow": [
        "Open a merchant/chargeback dispute",
        "Attach payment proof and seller correspondence",
    ],
    "lending_conduct_review": [
        "Review the lender's charges against the agreed terms",
        "Request the loan agreement and repayment schedule",
    ],
    "general_financial_triage": ["Route to a financial dispute officer for triage"],
    "public_infrastructure_complaint": [
        "Log with the responsible works department",
        "Confirm the exact street and local government area",
        "Attach photographs if available",
    ],
    "utility_complaint": [
        "Log with the responsible utility provider",
        "Confirm account/meter number if one exists",
    ],
    "sanitation_complaint": ["Log with the waste management authority"],
    "health_service_complaint": ["Log with the primary healthcare board"],
    "general_public_service_triage": ["Route to a public service officer for triage"],
    "general_triage": ["Route for manual triage"],
}

# Below this, the packet is flagged rather than presented as ready.
COMPLETENESS_THRESHOLD = 0.75


def route(case: "CompiledCase") -> dict:
    schema = schemas.get(case.domain)
    route_key, label = schema.routes.get(
        case.case_type, ("general_triage", "General triage queue")
    )
    return {
        "route": route_key,
        "label": label,
        "next_steps": NEXT_STEPS.get(route_key, NEXT_STEPS["general_triage"]),
    }


def evidence_status(case: "CompiledCase", uploaded: list[str] | None = None) -> dict:
    """Split evidence into mentioned / supplied / still outstanding.

    This is what makes the output case infrastructure rather than a chatbot reply: it
    tracks what the speaker SAID they have against what has actually been provided.
    """
    uploaded = uploaded or []
    mentioned = case.fields.get("evidence") or []
    if isinstance(mentioned, str):
        mentioned = [mentioned]

    supplied_flat = [u.lower() for u in uploaded]
    outstanding = [
        item for item in mentioned
        if not any(tok in u for u in supplied_flat
                   for tok in str(item).lower().split() if len(tok) > 3)
    ]
    return {
        "mentioned": list(mentioned),
        "supplied": uploaded,
        "outstanding": outstanding,
    }


def build_packet(case: "CompiledCase", uploaded_evidence: list[str] | None = None) -> dict:
    """The final artefact: an actionable case packet."""
    schema = schemas.get(case.domain)
    routing = route(case)
    completeness = case.completeness
    ready = completeness >= COMPLETENESS_THRESHOLD and not case.missing_information

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "compiler": schema.label,
        "domain": case.domain,
        "case_type": case.case_type,
        "status": "ready_for_review" if ready else "incomplete",
        "completeness": round(completeness, 3),
        "confidence": case.confidence,
        "user_reported": case.fields,
        "missing_information": case.missing_information,
        "outstanding_questions": case.questions,
        "evidence": evidence_status(case, uploaded_evidence),
        "routing": routing,
        "provenance": {
            "transcript": case.transcript,
            "extractor": case.extractor,
            "compile_latency_s": case.latency_s,
            "warnings": case.warnings,
        },
        "disclaimer": (
            "This packet records what the speaker reported. It is not legal, financial "
            "or medical advice, and it contains no determination of fault or "
            "entitlement. It has not been submitted to any external institution."
        ),
    }


def save_packet(packet: dict, out_dir: Path | None = None, name: str | None = None) -> Path:
    out_dir = out_dir or (config.DATA / "cases")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = name or f"{packet['domain']}_{packet['case_type']}_{stamp}.json"
    path = out_dir / filename
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_text(packet: dict) -> str:
    """Human-readable case packet, used by the CLI demo and the download view."""
    lines: list[str] = []
    add = lines.append

    add("=" * 62)
    add(f"  {packet['compiler'].upper()}")
    add(f"  {packet['case_type'].replace('_', ' ').upper()}")
    add("=" * 62)
    add(f"  status       : {packet['status']}")
    add(f"  completeness : {packet['completeness'] * 100:.0f}%")
    add(f"  confidence   : {packet['confidence']}")
    add("")

    add("  USER REPORTED")
    add("  " + "-" * 58)
    for key, value in packet["user_reported"].items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            add(f"  {key}:")
            for item in value:
                add(f"      - {item}")
        else:
            add(f"  {key}: {value}")
    add("")

    ev = packet["evidence"]
    if ev["mentioned"] or ev["supplied"]:
        add("  EVIDENCE")
        add("  " + "-" * 58)
        for item in ev["mentioned"]:
            mark = "[ok]" if item not in ev["outstanding"] else "[!!]"
            add(f"  {mark} {item}")
        for item in ev["supplied"]:
            add(f"  [up] {item} (uploaded)")
        add("")

    if packet["missing_information"]:
        add("  MISSING")
        add("  " + "-" * 58)
        for item in packet["missing_information"]:
            add(f"  [!!] {item}")
        add("")

    if packet["outstanding_questions"]:
        add("  QUESTIONS TO ASK")
        add("  " + "-" * 58)
        for i, q in enumerate(packet["outstanding_questions"], 1):
            add(f"  {i}. {q['question']}")
            add(f"     why: {q['why']}")
        add("")

    add("  ROUTING")
    add("  " + "-" * 58)
    add(f"  route: {packet['routing']['route']}")
    add(f"  desk : {packet['routing']['label']}")
    for step in packet["routing"]["next_steps"]:
        add(f"   - {step}")
    add("")

    if packet["provenance"]["warnings"]:
        add("  WARNINGS")
        add("  " + "-" * 58)
        for warning in packet["provenance"]["warnings"]:
            add(f"  [!] {warning}")
        add("")

    add("  " + "-" * 58)
    add(f"  extractor: {packet['provenance']['extractor']}")
    add("")
    for chunk in _wrap(packet["disclaimer"], 58):
        add(f"  {chunk}")
    add("=" * 62)
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out
