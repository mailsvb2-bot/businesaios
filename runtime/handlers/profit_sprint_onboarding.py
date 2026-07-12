from __future__ import annotations

from typing import Any

from runtime.ads import AdsApplyState, AdsPlan, plan_digest
from runtime.idempotency import make_idempotency_key
from runtime.ports.effects import EffectsPort
from runtime.tenancy import normalize_tenant_id
from runtime.ux import kb_ads_apply_pending

CANON_THIN_HANDLER = True

"""Profit Sprint onboarding handlers (runtime actions).

These handlers execute already-decided onboarding steps. They preserve tenant
scope and the exact accepted input as event payload; they do not choose business
strategy or create a competing planning authority.
"""

# Boundary anchors: this handler is allowed to depend on runtime public surfaces,
# not on core.* implementation modules. Keep these names visible so architecture
# locks can detect boundary drift without requiring the handler to duplicate
# business logic.
_PROFIT_SPRINT_RUNTIME_PUBLIC_SURFACES = (
    AdsApplyState,
    AdsPlan,
    plan_digest,
    make_idempotency_key,
    kb_ads_apply_pending,
)


def _context(payload: dict[str, Any], env: Any) -> tuple[str, str, str, str]:
    body = dict(payload or {})
    decision = getattr(env, "decision", None)
    decision_id = str(getattr(decision, "decision_id", "") or "").strip()
    correlation_id = str(getattr(decision, "correlation_id", "") or "").strip()
    tenant_id = normalize_tenant_id(
        body.get("tenant_id")
        or (getattr(decision, "tenant_id", None) if decision is not None else None)
        or getattr(env, "tenant_id", None)
    )
    user_id = str(body.get("user_id") or "").strip()
    if not decision_id:
        raise RuntimeError("DECISION_ID_REQUIRED")
    if not correlation_id:
        raise RuntimeError("CORRELATION_ID_REQUIRED")
    if not tenant_id:
        raise RuntimeError("TENANT_ID_REQUIRED")
    if not user_id:
        raise RuntimeError("USER_ID_REQUIRED")
    return decision_id, correlation_id, tenant_id, user_id


def _input_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def handle_onboarding_start(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = dict(payload or {})
    decision_id, correlation_id, tenant_id, user_id = _context(body, env)
    product_id = _input_value(body, "product_id")
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text="🚀 Profit Sprint: старт.\n\nСледуй шагам в меню автопилота.",
        reply_markup={"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "autopilot:menu"}]]},
        callback_query_id=body.get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_start@v1",
        track_payload={
            "tenant_id": tenant_id,
            "product_id": product_id,
            "step": "start",
        },
    )


def handle_onboarding_text(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = dict(payload or {})
    decision_id, correlation_id, tenant_id, user_id = _context(body, env)
    accepted_text = _input_value(body, "text", "value", "answer")
    if not accepted_text:
        raise RuntimeError("ONBOARDING_TEXT_REQUIRED")
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text="✅ Принято.",
        callback_query_id=body.get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_text@v1",
        track_payload={
            "tenant_id": tenant_id,
            "product_id": _input_value(body, "product_id"),
            "step": _input_value(body, "step", "field", "question") or "text",
            "value": accepted_text,
        },
    )


def handle_onboarding_lead_source(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = dict(payload or {})
    decision_id, correlation_id, tenant_id, user_id = _context(body, env)
    lead_source = _input_value(body, "lead_source", "value", "source")
    if not lead_source:
        raise RuntimeError("LEAD_SOURCE_REQUIRED")
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text="✅ Источник лидов выбран.",
        callback_query_id=body.get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_lead_source@v1",
        track_payload={
            "tenant_id": tenant_id,
            "product_id": _input_value(body, "product_id"),
            "step": "lead_source",
            "lead_source": lead_source,
        },
    )
