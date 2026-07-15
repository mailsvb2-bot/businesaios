from __future__ import annotations

from runtime.handler_impl.core.payloads import optional_dict, optional_str, require_mapping, required_int, required_str
from runtime.handlers.delivery_contract import delivery_kwargs


def _optional_plan_id(payload: dict) -> int | None:
    raw = payload.get("plan_id")
    if raw is None or raw == "":
        return None
    try:
        plan_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_PLAN_ID") from exc
    if plan_id <= 0:
        raise ValueError("INVALID_PLAN_ID")
    return plan_id


def _pricing_selector(payload: dict) -> tuple[str | None, int | None]:
    offer_id = optional_str(payload, "offer_id")
    plan_id = _optional_plan_id(payload)
    if not offer_id and plan_id is None:
        raise ValueError("OFFER_ID_OR_PLAN_ID_REQUIRED")
    return offer_id, plan_id


def handle_apply_pricing_change(payload, effects, env):
    payload = require_mapping(payload)
    offer_id, plan_id = _pricing_selector(payload)
    return effects.apply_pricing_change(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        tenant_id=required_str(payload, "tenant_id"),
        product_id=required_str(payload, "product_id"),
        environment=optional_str(payload, "environment"),
        offer_id=offer_id,
        plan_id=plan_id,
        new_price=required_int(payload, "new_price", min_value=1),
        pricing_version=required_str(payload, "pricing_version"),
        request_id=required_str(payload, "request_id"),
        reason=optional_str(payload, "reason"),
    )


def handle_request_pricing_change(payload, effects, env):
    payload = require_mapping(payload)
    offer_id, plan_id = _pricing_selector(payload)
    return effects.request_pricing_change(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        tenant_id=required_str(payload, "tenant_id"),
        product_id=required_str(payload, "product_id"),
        environment=optional_str(payload, "environment"),
        offer_id=offer_id,
        plan_id=plan_id,
        new_price=required_int(payload, "new_price", min_value=1),
        request_id=required_str(payload, "request_id"),
        suggested_pricing_version=optional_str(payload, "suggested_pricing_version"),
        reason=optional_str(payload, "reason"),
    )


def handle_reject_pricing_change(payload, effects, env):
    payload = require_mapping(payload)
    return effects.reject_pricing_change(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        tenant_id=required_str(payload, "tenant_id"),
        product_id=optional_str(payload, "product_id"),
        request_id=required_str(payload, "request_id"),
        reason=optional_str(payload, "reason"),
    )


def handle_select_tariff(payload, effects, env):
    payload = require_mapping(payload)
    expected_price = payload.get("expected_price")
    plan_id = payload.get("plan_id")
    return effects.select_tariff(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        product_id=required_str(payload, "product_id"),
        user_id=required_str(payload, "user_id"),
        tariff=required_str(payload, "tariff"),
        days=required_int(payload, "days", min_value=1),
        period=required_str(payload, "period"),
        amount=required_int(payload, "amount", min_value=1),
        plan_id=(int(plan_id) if plan_id is not None else None),
        title=optional_str(payload, "title"),
        expected_price=(int(expected_price) if expected_price is not None else None),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        **delivery_kwargs(payload),
    )
