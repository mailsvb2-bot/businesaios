from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_OWNER_DECISION_PROVENANCE = True
OWNER_DECISION_DRAFT_SOURCE = "owner_decision_draft"
OWNER_DECISION_DRAFT_VERIFICATION = "server_ledger"


def _text(value: object) -> str:
    return str(value or "").strip()


def normalize_owner_decision_provenance(value: object, *, require_verified: bool = True) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    raw = dict(value)
    if _text(raw.get("source")) != OWNER_DECISION_DRAFT_SOURCE:
        return {}
    verification = _text(raw.get("verification"))
    if require_verified and verification != OWNER_DECISION_DRAFT_VERIFICATION:
        return {}
    required = {
        "tenant_id": _text(raw.get("tenant_id")),
        "business_id": _text(raw.get("business_id")),
        "run_id": _text(raw.get("run_id")),
        "decision_id": _text(raw.get("decision_id")),
        "action_id": _text(raw.get("action_id")),
        "action_type": _text(raw.get("action_type")),
    }
    if not all(required.values()) or required["action_type"] != "send_message@v1":
        return {}
    return {
        "source": OWNER_DECISION_DRAFT_SOURCE,
        "verification": verification,
        **required,
    }


__all__ = [
    "CANON_OWNER_DECISION_PROVENANCE",
    "OWNER_DECISION_DRAFT_SOURCE",
    "OWNER_DECISION_DRAFT_VERIFICATION",
    "normalize_owner_decision_provenance",
]
