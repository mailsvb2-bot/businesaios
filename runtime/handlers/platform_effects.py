from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.verification.evidence_types import evidence_status_is_positive
from runtime.handler_impl.core.payloads import (
    optional_dict,
    optional_str,
    require_mapping,
    required_str,
)
from runtime.handlers.delivery_contract import delivery_kwargs
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True


def _trusted_delivery_evidence(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = value.get(key)
        if not isinstance(candidate, Mapping):
            continue
        source = str(candidate.get("source") or "").strip()
        positive = (
            candidate.get("verified") is True
            or evidence_status_is_positive(candidate.get("status"))
        )
        if source and positive:
            return dict(candidate)
    return None


def handle_enqueue_evolution_job(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
) -> Any:
    body = require_mapping(payload)
    return effects.enqueue_evolution_job(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        tenant_id=required_str(body, "tenant_id"),
        user_id=required_str(body, "user_id"),
        job_kind=required_str(body, "job_kind"),
        payload=optional_dict(body, "payload"),
        **delivery_kwargs(body),
    )


def handle_suggest_offer_patch(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
) -> Any:
    body = require_mapping(payload)
    notify_user_id = optional_str(body, "notify_user_id")
    result = effects.suggest_offer_patch(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        tenant_id=required_str(body, "tenant_id"),
        product=required_str(body, "product"),
        env=required_str(body, "env"),
        offer_id=required_str(body, "offer_id"),
        action=required_str(body, "action"),
        notify_user_id=notify_user_id,
        callback_query_id=optional_str(body, "callback_query_id"),
        **delivery_kwargs(body),
    )
    if not notify_user_id:
        return result

    normalized = dict(result) if isinstance(result, Mapping) else {"result": result}
    notification = normalized.get("notification")
    proof = _trusted_delivery_evidence(notification)
    notification_ok = (
        bool(notification.get("ok"))
        if isinstance(notification, Mapping)
        else bool(notification)
    )
    verified = bool(notification_ok and proof)
    normalized.update(
        {
            "ok": verified,
            "status": "verified" if verified else "failed",
            "router_evidence": proof if verified else None,
        }
    )
    return normalized


def handle_apply_offer_patch(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
) -> Any:
    body = require_mapping(payload)
    mode = str(body.get("mode") or "dry_run").strip().casefold()
    if mode not in {"dry_run", "apply", "rollback"}:
        raise ValueError("INVALID_OFFER_PATCH_MODE")
    patch = optional_dict(body, "patch")
    if mode in {"dry_run", "apply"} and not patch:
        raise ValueError("OFFER_PATCH_REQUIRED")

    return effects.apply_offer_patch(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        tenant_id=required_str(body, "tenant_id"),
        product=required_str(body, "product"),
        env=required_str(body, "env"),
        offer_id=required_str(body, "offer_id"),
        patch=patch or {},
        mode=mode,
        notify_user_id=optional_str(body, "notify_user_id"),
        callback_query_id=optional_str(body, "callback_query_id"),
        **delivery_kwargs(body),
    )


__all__ = [
    "handle_apply_offer_patch",
    "handle_enqueue_evolution_job",
    "handle_suggest_offer_patch",
]
