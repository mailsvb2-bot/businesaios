from __future__ import annotations

from typing import Any, Mapping

from runtime._internal.effect_results import canonical_effect_result
from runtime._internal.effect_types import EffectActionType, require_effect_action_type


def evidence_contract_fields() -> tuple[str, ...]:
    return (
        "source",
        "action_type",
        "status",
        "summary",
        "external_refs",
        "confidence",
        "payload",
    )
def effect_result_to_evidence(action_type: str | EffectActionType, result: Mapping[str, Any] | None) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    normalized = canonical_effect_result(key, result or {})
    payload = {
        "source": "effect_router",
        "action_type": str(key),
        "status": str(normalized.get("verification_status") or normalized.get("status") or "unknown"),
        "summary": str(normalized.get("error") or normalized.get("status") or "").strip(),
        "external_refs": list(normalized.get("external_refs") or []),
        "confidence": float(normalized.get("verification_confidence") or 0.0),
        "payload": {
            "status": normalized.get("status"),
            "ok": normalized.get("ok"),
            "retryable": normalized.get("retryable"),
            "external_id": normalized.get("external_id"),
            "data": dict(normalized.get("data") or {}),
        },
    }
    return payload
