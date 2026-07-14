from __future__ import annotations

from typing import Any

from runtime.handler_impl.core.payloads import (
    optional_dict,
    optional_str,
    require_mapping,
    required_str,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True


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
    )


def handle_suggest_offer_patch(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
) -> Any:
    body = require_mapping(payload)
    return effects.suggest_offer_patch(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        tenant_id=required_str(body, "tenant_id"),
        product=required_str(body, "product"),
        env=required_str(body, "env"),
        offer_id=required_str(body, "offer_id"),
        action=required_str(body, "action"),
        notify_user_id=optional_str(body, "notify_user_id"),
        callback_query_id=optional_str(body, "callback_query_id"),
    )


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
    )


__all__ = [
    "handle_apply_offer_patch",
    "handle_enqueue_evolution_job",
    "handle_suggest_offer_patch",
]
