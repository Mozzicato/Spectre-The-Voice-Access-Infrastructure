"""Domain schemas.

The compiler engine is identical across domains. Only this file changes. That is the
entire scalability claim: adding a fourth vertical means adding a schema here, not
building a fourth application.

Every schema separates what the USER REPORTED from what the SYSTEM CONCLUDED. The system
never asserts a legal or financial determination - it structures a claim and says what is
missing. See `docs/RESPONSIBLE_AI.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Field:
    name: str
    description: str
    required: bool = False
    kind: str = "string"  # string | list | number | date


@dataclass(frozen=True)
class Schema:
    key: str
    label: str
    icon: str
    case_types: tuple[str, ...]
    fields: tuple[Field, ...]
    routes: dict = field(default_factory=dict)

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)

    def json_schema(self) -> dict:
        """JSON Schema for structured extraction."""
        kind_map = {
            "string": {"type": ["string", "null"]},
            "number": {"type": ["number", "null"]},
            "date": {"type": ["string", "null"],
                     "description": "ISO-8601 where possible, else the phrase as spoken"},
            "list": {"type": "array", "items": {"type": "string"}},
        }
        props = {
            "case_type": {
                "type": "string",
                "enum": list(self.case_types),
                "description": "The single best-fitting case type.",
            }
        }
        for f in self.fields:
            if f.name == "case_type":
                continue
            entry = dict(kind_map[f.kind])
            entry["description"] = f.description
            props[f.name] = entry

        props["missing_information"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required fields that the speaker did not provide.",
        }
        props["confidence"] = {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "How confident the extraction is, given transcript quality.",
        }
        return {
            "type": "object",
            "properties": props,
            "required": ["case_type", "missing_information"],
        }


# --------------------------------------------------------------------------------------

LEGAL = Schema(
    key="legal",
    label="Legal Case Compiler",
    icon="scales",
    case_types=(
        "tenancy_dispute", "employment_dispute", "consumer_dispute",
        "land_dispute", "family_matter", "other_legal",
    ),
    fields=(
        Field("parties", "Every person/organisation mentioned and their role "
                         "(e.g. 'landlord', 'employer', 'tenant').", True, "list"),
        Field("location", "State/city/area where the matter took place.", True),
        Field("events", "What happened, in order, each as one short factual sentence.",
              True, "list"),
        Field("dates", "Dates or time references mentioned.", True, "list"),
        Field("amounts", "Money amounts mentioned, with what each refers to.", True, "list"),
        Field("claims", "What the speaker says they are owed or entitled to.", False, "list"),
        Field("actions_taken", "Steps the speaker has already taken.", False, "list"),
        Field("evidence", "Evidence the speaker mentions having.", False, "list"),
        Field("urgency", "immediate | soon | routine, based on what was said.", False),
    ),
    routes={
        "tenancy_dispute": ("legal_aid_review", "Tenancy matters desk / legal aid clinic"),
        "employment_dispute": ("labour_review", "Labour office / employment legal aid"),
        "consumer_dispute": ("consumer_protection_review",
                             "Consumer protection complaint workflow"),
        "land_dispute": ("legal_aid_review", "Land matters / legal aid clinic"),
        "family_matter": ("legal_aid_review", "Family law legal aid"),
        "other_legal": ("general_legal_triage", "General legal triage queue"),
    },
)

FINANCIAL = Schema(
    key="financial",
    label="Financial Dispute Compiler",
    icon="bank",
    case_types=(
        "failed_transfer", "unauthorized_transaction", "failed_atm_withdrawal",
        "payment_dispute", "loan_dispute", "other_financial",
    ),
    fields=(
        Field("account_holder", "Who the account belongs to, if stated.", False),
        Field("institution", "Bank(s)/provider(s) named.", True, "list"),
        Field("transaction_type", "transfer | withdrawal | card payment | loan | other.",
              True),
        Field("amount", "The disputed amount, digits only where stated.", True, "number"),
        Field("currency", "Currency, default NGN for naira.", False),
        Field("date", "When the transaction happened.", True, "date"),
        Field("transaction_reference",
              "Reference/session ID, digits joined with no spaces.", False),
        Field("recipient", "Who the money was going to.", False),
        Field("reported_status", "What the speaker says the current status is.", True),
        Field("problem", "One sentence stating the dispute.", True),
        Field("actions_taken", "Steps already taken (branch visit, dispute form, calls).",
              False, "list"),
        Field("evidence", "Evidence mentioned (alert, receipt, screenshot, chat).",
              False, "list"),
    ),
    routes={
        "failed_transfer": ("bank_dispute_workflow", "Bank transfer dispute / NIBSS reversal"),
        "unauthorized_transaction": ("fraud_review", "Fraud desk - unauthorised transaction"),
        "failed_atm_withdrawal": ("bank_dispute_workflow", "ATM dispense error reversal"),
        "payment_dispute": ("merchant_dispute_workflow", "Merchant/chargeback dispute"),
        "loan_dispute": ("lending_conduct_review", "Lending conduct / charges review"),
        "other_financial": ("general_financial_triage", "General financial triage queue"),
    },
)

PUBLIC_SERVICE = Schema(
    key="public_service",
    label="Citizen Complaint Compiler",
    icon="government",
    case_types=(
        "streetlight_failure", "road_or_drainage", "water_supply",
        "electricity_supply", "waste_management", "health_facility",
        "other_public_service",
    ),
    fields=(
        Field("location", "Street/area/LGA/state, as precisely as stated.", True),
        Field("agency", "Responsible agency/body, if named.", False),
        Field("problem", "One sentence stating the problem.", True),
        Field("duration", "How long it has been going on.", True),
        Field("previous_reports", "Prior reports made, with counts/dates if stated.",
              True, "list"),
        Field("previous_actions", "What the speaker or others already did.", False, "list"),
        Field("impact", "Who/what is affected and how, including numbers if stated.",
              True, "list"),
        Field("evidence", "Evidence mentioned (photos, letters, receipts).", False, "list"),
    ),
    routes={
        "streetlight_failure": ("public_infrastructure_complaint",
                                "LGA works dept - street lighting"),
        "road_or_drainage": ("public_infrastructure_complaint",
                             "Works & infrastructure - roads/drainage"),
        "water_supply": ("utility_complaint", "Water corporation complaint workflow"),
        "electricity_supply": ("utility_complaint", "DisCo complaint / metering workflow"),
        "waste_management": ("sanitation_complaint", "Waste management authority"),
        "health_facility": ("health_service_complaint", "Primary healthcare board"),
        "other_public_service": ("general_public_service_triage",
                                 "General public service triage"),
    },
)

SCHEMAS: dict[str, Schema] = {s.key: s for s in (LEGAL, FINANCIAL, PUBLIC_SERVICE)}

# Routing from the top-level domain classifier to a schema.
DOMAIN_HINTS = {
    "legal": LEGAL.key,
    "financial": FINANCIAL.key,
    "finance": FINANCIAL.key,
    "fin": FINANCIAL.key,
    "public_service": PUBLIC_SERVICE.key,
    "public": PUBLIC_SERVICE.key,
    "pub": PUBLIC_SERVICE.key,
}


def get(key: str) -> Schema:
    resolved = DOMAIN_HINTS.get(key.lower(), key.lower())
    if resolved not in SCHEMAS:
        raise KeyError(f"unknown domain {key!r}; choose from {sorted(SCHEMAS)}")
    return SCHEMAS[resolved]
