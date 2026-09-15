"""Adaptive question engine: voice form-filling without the form.

We never present a 20-field form. We extract what the story already contains, work out
which required fields are still empty, and ask only for those - one plain question at a
time, in the order that matters most for the case.

Question wording is templated rather than generated. The system asks for facts; it must
not improvise a question that implies a legal position or leads the speaker's answer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app import schemas

if TYPE_CHECKING:
    from app.compiler import CompiledCase

# Field -> (question, why it matters). Keyed by schema then field, with a shared fallback.
QUESTIONS: dict[str, dict[str, tuple[str, str]]] = {
    "legal": {
        "location": ("What state or area is this matter in?",
                     "Determines which court or legal aid office can act."),
        "parties": ("Who exactly is involved, and what is their relationship to you?",
                    "A case needs named parties."),
        "events": ("Can you walk me through what happened, step by step?",
                   "The sequence of events is the substance of the claim."),
        "dates": ("When did this start, and when did the most recent thing happen?",
                  "Time limits can apply to legal claims."),
        "amounts": ("How much money is involved, and what is it for?",
                    "Determines the value of the claim."),
        "claims": ("What outcome are you asking for?",
                   "States what relief is being sought."),
        "evidence": ("Do you have any documents, receipts, messages or photos?",
                     "Evidence decides whether a claim can be pursued."),
    },
    "financial": {
        "institution": ("Which bank or service was this with?",
                        "The dispute has to be raised with the right institution."),
        "amount": ("Exactly how much money is involved?",
                   "The disputed amount must be exact."),
        "date": ("What date and roughly what time did this happen?",
                 "Banks locate transactions by date and time."),
        "transaction_reference": (
            "Do you have the transaction reference or session ID? "
            "You can read it out one digit at a time.",
            "A reference lets the bank find the transaction immediately."),
        "transaction_type": ("Was this a transfer, a withdrawal, a card payment, "
                             "or something else?",
                             "Different transaction types follow different workflows."),
        "reported_status": ("What has the bank told you so far, if anything?",
                            "Shows whether the dispute has already been logged."),
        "problem": ("In one sentence, what went wrong?",
                    "States the dispute."),
        "recipient": ("Who was the money going to?",
                      "Identifies the receiving account."),
    },
    "public_service": {
        "location": ("What is the street name and area, and which local government?",
                     "The complaint must be routed to the responsible authority."),
        "problem": ("What exactly is the problem?", "States the complaint."),
        "duration": ("How long has this been going on?",
                     "Duration affects priority."),
        "previous_reports": ("Have you reported this before? If so, to whom, and when?",
                             "Prior reports escalate a complaint."),
        "impact": ("Who is affected by this, and how?",
                   "Impact determines priority."),
        "agency": ("Do you know which agency is responsible?",
                   "Helps route the complaint directly."),
        "evidence": ("Do you have photos or any letters about this?",
                     "Evidence strengthens the complaint."),
    },
}

# Asked first when several fields are missing: these unblock routing.
PRIORITY = ("location", "amount", "date", "institution", "problem",
            "parties", "duration", "transaction_type")


def _fallback(field_name: str) -> tuple[str, str]:
    pretty = field_name.replace("_", " ")
    return (f"Can you tell me about the {pretty}?",
            f"The case record needs {pretty}.")


def build_questions(case: "CompiledCase", schema: schemas.Schema | None = None,
                    limit: int = 5) -> list[dict]:
    """One question per missing required field, most important first."""
    schema = schema or schemas.get(case.domain)
    bank = QUESTIONS.get(schema.key, {})

    def sort_key(name: str) -> tuple[int, str]:
        return (PRIORITY.index(name) if name in PRIORITY else len(PRIORITY), name)

    questions = []
    for name in sorted(case.missing_information, key=sort_key)[:limit]:
        text, why = bank.get(name, _fallback(name))
        questions.append({"field": name, "question": text, "why": why})
    return questions


def next_question(case: "CompiledCase") -> dict | None:
    return case.questions[0] if case.questions else None


def apply_answer(case: "CompiledCase", field_name: str, answer: str) -> "CompiledCase":
    """Fold a spoken answer back into the case and recompute what is still missing.

    The answer is stored as the speaker gave it. This is a claim record, not a finding.
    """
    from app.compiler import detect_missing

    schema = schemas.get(case.domain)
    spec = next((f for f in schema.fields if f.name == field_name), None)
    answer = (answer or "").strip()
    if not answer:
        return case

    if spec is not None and spec.kind == "list":
        existing = case.fields.get(field_name) or []
        if not isinstance(existing, list):
            existing = [existing]
        case.fields[field_name] = existing + [answer]
    elif spec is not None and spec.kind == "number":
        from app.normalize import spoken_numbers_to_values
        values = spoken_numbers_to_values(answer)
        case.fields[field_name] = values[0] if values else answer
    else:
        case.fields[field_name] = answer

    case.missing_information = detect_missing(case.fields, schema)
    case.questions = build_questions(case, schema)
    return case
