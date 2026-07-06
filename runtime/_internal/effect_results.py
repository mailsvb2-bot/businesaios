from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from time import time
from typing import Any

from runtime._internal.effect_types import EffectActionType, require_effect_action_type


class EffectResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    RETRYABLE = "retryable"
    SKIPPED = "skipped"
def _text(value: Any) -> str:
    return str(value or "").strip()
def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
def _safe_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
def _safe_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "ok", "success", "succeeded", "verified"}:
            return True
        if lowered in {"0", "false", "no", "off", "failure", "failed", "error"}:
            return False
    if value is None:
        return default
    return bool(value)
def result_contract_fields() -> tuple[str, ...]:
    return (
        "status",
        "action_type",
        "ok",
        "retryable",
        "data",
        "error",
        "external_id",
        "external_refs",
        "verification_status",
        "verification_confidence",
        "cost",
        "evidence",
        "timestamp",
    )
def normalize_effect_result_status(raw: Any, *, ok: bool, retryable: bool) -> EffectResultStatus:
    text = _text(raw).lower().replace(" ", "_")
    if retryable or text in {"retryable", "temporary_failure", "rate_limited", "timeout", "transient_error"}:
        return EffectResultStatus.RETRYABLE
    if text in {"skipped", "noop", "not_required"}:
        return EffectResultStatus.SKIPPED
    if text in {"success", "ok", "verified", "executed", "completed", "accepted"}:
        return EffectResultStatus.SUCCESS
    if text in {"failure", "failed", "error", "denied", "blocked"}:
        return EffectResultStatus.FAILURE
    return EffectResultStatus.SUCCESS if ok else EffectResultStatus.FAILURE
def success_result(action_type: str | EffectActionType, **data: Any) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    payload = dict(data)
    payload.setdefault("ok", True)
    payload.setdefault("status", EffectResultStatus.SUCCESS)
    payload.setdefault("action_type", str(key))
    return canonical_effect_result(key, payload)
def failure_result(action_type: str | EffectActionType, *, error: str, retryable: bool = False, **data: Any) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    payload = dict(data)
    payload.update({
        "ok": False,
        "error": _text(error),
        "retryable": bool(retryable),
        "status": EffectResultStatus.RETRYABLE if retryable else EffectResultStatus.FAILURE,
        "action_type": str(key),
    })
    return canonical_effect_result(key, payload)
def retryable_result(action_type: str | EffectActionType, *, error: str, **data: Any) -> dict[str, Any]:
    return failure_result(action_type, error=error, retryable=True, **data)
def canonical_effect_result(action_type: str | EffectActionType, raw_result: Any) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    payload = _safe_dict(raw_result)
    ok = _safe_bool(payload.get("ok"), default=_safe_bool(payload.get("success"), default=False))
    if "ok" not in payload and "success" in payload:
        ok = _safe_bool(payload.get("success"), default=False)
    if not payload:
        ok = True
    retryable = _safe_bool(payload.get("retryable"), default=False)
    status = normalize_effect_result_status(payload.get("status") or payload.get("code"), ok=ok, retryable=retryable)
    external_refs_raw = payload.get("external_refs")
    external_refs: list[str] = []
    if isinstance(external_refs_raw, (list, tuple, set)):
        external_refs = [str(item).strip() for item in external_refs_raw if str(item).strip()]
    elif _text(payload.get("external_ref")):
        external_refs = [_text(payload.get("external_ref"))]
    verification_status = _text(payload.get("verification_status") or payload.get("evidence_status"))
    if not verification_status:
        verification_status = "verified" if ok else ("unverified" if status is not EffectResultStatus.SKIPPED else "skipped")
    verification_confidence = _safe_float(payload.get("verification_confidence") or payload.get("confidence"))
    if verification_confidence is None:
        verification_confidence = 1.0 if ok else (0.5 if retryable else 0.0)
    data = _safe_dict(payload.get("data"))
    passthrough = {
        key_name: value
        for key_name, value in payload.items()
        if key_name
        not in {
            "status", "code", "action_type", "ok", "success", "retryable", "data", "error", "external_id",
            "external_ref", "external_refs", "verification_status", "evidence_status", "verification_confidence",
            "confidence", "cost", "timestamp", "evidence",
        }
    }
    if passthrough:
        data = {**data, **passthrough}
    explicit_timestamp = _safe_float(payload.get("timestamp"))
    if explicit_timestamp is not None:
        resolved_timestamp = float(explicit_timestamp)
    else:
        mode = _text(payload.get("mode")).lower()
        if status is EffectResultStatus.SKIPPED or mode in {"noop", "dedup", "best_effort"}:
            # Hermetic / no-op / deduplicated results must stay deterministic across
            # replay. Real connector timestamps should be passed explicitly by the
            # effect implementation when needed.
            resolved_timestamp = 0.0
        else:
            resolved_timestamp = float(time())
    result = {
        "status": str(status),
        "action_type": str(key),
        "ok": bool(ok),
        "retryable": bool(retryable),
        "data": data,
        "error": _text(payload.get("error") or payload.get("message")) or None,
        "external_id": _text(payload.get("external_id") or payload.get("id")) or None,
        "external_refs": external_refs,
        "verification_status": verification_status,
        "verification_confidence": float(max(0.0, min(1.0, float(verification_confidence)))),
        "cost": _safe_float(payload.get("cost")),
        "timestamp": resolved_timestamp,
    }
    for key_name, value in passthrough.items():
        result.setdefault(key_name, value)
    if isinstance(payload.get("evidence"), Mapping):
        result["evidence"] = dict(payload["evidence"])
    return result
