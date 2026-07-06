from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_EFFECT_OUTCOME_VOCABULARY = True

_VERIFIED_ALIASES = {
    "accepted",
    "created",
    "done",
    "executed",
    "exists",
    "ok",
    "passed",
    "present",
    "success",
    "succeeded",
    "verified",
}
_UNVERIFIED_ALIASES = {
    "denied",
    "error",
    "failed",
    "failure",
    "insufficient_observed_effect",
    "invalid",
    "missing_evidence",
    "not_found",
    "rejected",
    "unverified",
    "verification_failed",
}
_RETRYABLE_ALIASES = {
    "rate_limited",
    "retryable",
    "temporary_failure",
    "timeout",
    "transient_error",
}
_SKIPPED_ALIASES = {"noop", "not_required", "skipped"}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def normalize_outcome_status(
    value: object,
    *,
    verified: object | None = None,
    retryable: object | None = None,
    default: str = "unknown",
) -> str:
    text = _text(value).casefold()
    if bool(retryable) or text in _RETRYABLE_ALIASES:
        return "retryable"
    if text in _SKIPPED_ALIASES:
        return "skipped"
    if text == "missing_external_confirmation":
        return "missing_external_confirmation"
    if text in _VERIFIED_ALIASES:
        return "verified"
    if text in _UNVERIFIED_ALIASES:
        return "unverified"
    if verified is True:
        return "verified"
    if verified is False:
        return "unverified"
    return default


def outcome_is_verified(value: object, *, verified: object | None = None, retryable: object | None = None) -> bool:
    return normalize_outcome_status(value, verified=verified, retryable=retryable, default="unknown") == "verified"


def normalize_outcome_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = _safe_dict(payload)
    status = normalize_outcome_status(
        raw.get("verification_status") or raw.get("status") or raw.get("code"),
        verified=raw.get("verified"),
        retryable=raw.get("retryable"),
    )
    verified = outcome_is_verified(status, verified=raw.get("verified"), retryable=raw.get("retryable"))
    normalized = dict(raw)
    normalized["verified"] = verified
    normalized["status"] = status
    normalized.setdefault("verification_status", status)
    normalized.setdefault("evidence_status", status)
    normalized["retryable"] = bool(raw.get("retryable", status == "retryable"))
    return normalized


__all__ = [
    "CANON_EFFECT_OUTCOME_VOCABULARY",
    "normalize_outcome_payload",
    "normalize_outcome_status",
    "outcome_is_verified",
]
