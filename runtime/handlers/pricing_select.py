from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.actions import ACTION_PRICING_SELECT_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.ports.effects import EffectsPort
from runtime.pricing import PricingRouteViolation, PricingSelectionContext

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_PRICING_SELECT_V1


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        value = delivery.get(key)
        if isinstance(value, Mapping) and str(value.get("source") or "").strip():
            return dict(value)
    return None


def _blocked_message(*, payload: dict[str, Any], effects: EffectsPort, decision_id: str, correlation_id: str, text: str, reason: str, exc: Exception) -> Any:
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=str(payload.get("tenant_id") or "").strip(),
        user_id=str(payload.get("user_id") or ""),
        text=text,
        track_event_type="pricing_select_blocked@v1",
        track_payload=blocked_error_payload(reason=reason, exc=exc),
    )


def handle_pricing_select(payload: dict[str, Any], effects: EffectsPort, env: Any, *, selection_service: Any) -> Any:
    p = dict(payload or {})
    try:
        route = extract_strict_route_from_envelope(payload=p, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = best_effort_route_ids(payload=p, env=env)
        return _blocked_message(
            payload=p,
            effects=effects,
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            text=safe_route_blocked_text("Pricing"),
            reason="route_violation",
            exc=exc,
        )
    if selection_service is None:
        raise RuntimeError("boot failure: pricing selection_service must be wired before handler dispatch")

    try:
        tenant_id = str(p.get("tenant_id") or "").strip()
        product_id = str(p.get("product_id") or "").strip()
        user_id = str(p.get("user_id") or "").strip()
        if not tenant_id:
            raise PricingRouteViolation("tenant_id is required")
        if not product_id:
            raise PricingRouteViolation("product_id is required")
        if not user_id:
            raise PricingRouteViolation("user_id is required")

        ctx = PricingSelectionContext(
            tenant_id=tenant_id,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            issuer_id=route.issuer_id,
            action=route.action,
        )
        selection_result = selection_service.select(
            ctx=ctx,
            candidates=list(p.get("candidates") or []),
            evidence=dict(p.get("evidence") or {}),
        )
        selected = selection_result.get("selected") if isinstance(selection_result, Mapping) else None
        selected_offer = dict(selected) if isinstance(selected, Mapping) else {}
        text = str(
            selected_offer.get("message")
            or selected_offer.get("title")
            or f"💸 Pricing selected: {bool(selected_offer)}"
        )
        delivery = effects.send_message(
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            text=text,
            track_event_type=ACTION_NAME,
            track_payload={
                "tenant_id": tenant_id,
                "product_id": product_id,
                "offer_id": str(selected_offer.get("offer_id") or ""),
                "selected": bool(selected_offer),
            },
        )
        evidence = _delivery_evidence(delivery)
        delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
        return {
            "ok": delivery_ok,
            "status": "verified" if delivery_ok and evidence else "failed",
            "selection": selected_offer,
            "selection_result": dict(selection_result) if isinstance(selection_result, Mapping) else {},
            "delivery": delivery,
            "router_evidence": evidence,
        }
    except PricingRouteViolation as exc:
        return _blocked_message(
            payload=p,
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            text=safe_route_blocked_text("Pricing"),
            reason="pricing_route_violation",
            exc=exc,
        )
