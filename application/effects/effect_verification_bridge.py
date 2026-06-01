from __future__ import annotations

from typing import Any, Mapping

from application.effects.canonical_execution_feedback import canonical_execution_feedback
from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified

CANON_EFFECT_VERIFICATION_BRIDGE = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _text(value)
    return [text] if text else []


def normalize_router_evidence(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = _safe_dict(payload)
    if not raw:
        return {}

    evidence_block = _safe_dict(raw.get("evidence"))
    payload_block = _safe_dict(evidence_block.get("payload"))
    data_block = _safe_dict(raw.get("data"))
    status = _text(
        raw.get("verification_status")
        or evidence_block.get("status")
        or raw.get("status")
        or raw.get("code")
    )
    status = normalize_outcome_status(status, verified=raw.get("ok", raw.get("verified", None)), retryable=raw.get("retryable", payload_block.get("retryable", False)), default="unknown")

    confidence = raw.get("verification_confidence")
    if confidence in {None, ""}:
        confidence = evidence_block.get("confidence")
    if confidence in {None, ""}:
        confidence = 1.0 if bool(raw.get("ok", raw.get("verified", False))) else 0.0

    external_refs = (
        _safe_list(raw.get("external_refs"))
        or _safe_list(evidence_block.get("external_refs"))
        or _safe_list(payload_block.get("external_refs"))
        or _safe_list(data_block.get("external_refs"))
    )

    message = _text(
        raw.get("error")
        or raw.get("message")
        or evidence_block.get("summary")
        or payload_block.get("message")
        or data_block.get("message")
    )

    verified = outcome_is_verified(status, verified=raw.get("verified", raw.get("ok", None)), retryable=raw.get("retryable", payload_block.get("retryable", False)))

    normalized = {
        "verified": verified,
        "status": status,
        "code": _text(raw.get("code") or status) or status,
        "message": message,
        "confidence": float(confidence or 0.0),
        "external_refs": external_refs,
        "action_type": _text(raw.get("action_type") or evidence_block.get("action_type")),
        "external_id": _text(raw.get("external_id") or payload_block.get("external_id")),
        "retryable": bool(raw.get("retryable", payload_block.get("retryable", False))),
        "source": _text(evidence_block.get("source") or raw.get("source") or "effect_router"),
    }
    return normalized


def normalize_feedback_contract(feedback: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(feedback)
    if not payload:
        return {}

    normalized = dict(payload)
    router_result = extract_router_result_from_feedback(payload)
    if router_result:
        normalized.setdefault("verified", bool(router_result.get("verified", False)))
        normalized["verification_status"] = normalize_outcome_status(
            normalized.get("verification_status") or router_result.get("status") or "unknown",
            verified=normalized.get("verified", router_result.get("verified")),
            retryable=router_result.get("retryable"),
            default="unknown",
        )
        normalized["verification_confidence"] = (
            normalized.get("verification_confidence")
            if normalized.get("verification_confidence") not in {None, ""}
            else router_result.get("confidence")
        )
        normalized["external_refs"] = list(
            _safe_list(normalized.get("external_refs")) or _safe_list(router_result.get("external_refs"))
        )
        evidence = _safe_dict(normalized.get("evidence"))
        evidence.setdefault("router_result", dict(router_result))
        normalized["evidence"] = evidence
        normalized.setdefault("evidence_status", normalized.get("verification_status"))
    normalized["execution_feedback"] = canonical_execution_feedback(feedback=normalized)
    return normalized


def extract_router_result_from_feedback(feedback: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(feedback)
    if not payload:
        return {}
    evidence = _safe_dict(payload.get("evidence"))
    candidates = [
        _safe_dict(evidence.get("router_result")),
        evidence if evidence.get("source") == "effect_router" or "payload" in evidence else {},
        _safe_dict(payload.get("router_result")),
    ]
    for candidate in candidates:
        normalized = normalize_router_evidence(candidate)
        if normalized:
            return normalized
    return {}


__all__ = [
    "CANON_EFFECT_VERIFICATION_BRIDGE",
    "extract_router_result_from_feedback",
    "normalize_feedback_contract",
    "normalize_router_evidence",
]
