from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime._internal.effect_results import canonical_effect_result
from runtime._internal.effect_types import EffectActionType, require_effect_action_type


def evidence_contract_fields() -> tuple[str, ...]:
    return (
        "source",
        "action_type",
        "verified",
        "status",
        "summary",
        "external_refs",
        "confidence",
        "payload",
    )


def _verification_is_positive(*, status: object, ok: object) -> bool:
    normalized = str(status or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"verified", "observed", "success", "ok", "accepted", "executed", "completed"}:
        return True
    if normalized in {"unverified", "failed", "failure", "error", "pending", "retryable", "skipped", "unknown"}:
        return False
    return bool(ok)


def effect_result_to_evidence(action_type: str | EffectActionType, result: Mapping[str, Any] | None) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    normalized = canonical_effect_result(key, result or {})
    verification_status = str(normalized.get("verification_status") or normalized.get("status") or "unknown")
    payload = {
        "source": "effect_router",
        "action_type": str(key),
        "verified": _verification_is_positive(status=verification_status, ok=normalized.get("ok")),
        "status": verification_status,
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


__all__ = ["effect_result_to_evidence", "evidence_contract_fields"]
