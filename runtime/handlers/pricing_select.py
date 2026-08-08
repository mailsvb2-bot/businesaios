from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.offers.offer_catalog_resolver import OfferCatalogResolver
from runtime.actions import ACTION_PRICING_SELECT_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.delivery_contract import delivery_kwargs
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


def _blocked_message(
    *, payload: dict[str, Any], effects: EffectsPort, decision_id: str, correlation_id: str,
    text: str, reason: str, exc: Exception,
) -> dict[str, Any]:
    delivery = effects.send_message(
        decision_id=decision_id, correlation_id=correlation_id,
        tenant_id=str(payload.get("tenant_id") or "").strip(), user_id=str(payload.get("user_id") or ""),
        text=text, track_event_type="pricing_select_blocked@v1",
        track_payload=blocked_error_payload(reason=reason, exc=exc), **delivery_kwargs(payload),
    )
    return {"ok": False, "status": "blocked", "reason": str(reason), "delivery": delivery, "router_evidence": None}


def _legacy_shortlist(raw: object) -> tuple[list[str] | None, dict[str, object]]:
    if raw is None:
        return None, {}
    if not isinstance(raw, list):
        raise PricingRouteViolation("candidates must be a list")
    offer_ids: list[str] = []
    scores: dict[str, object] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise PricingRouteViolation("pricing candidate must be an object")
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id or offer_id in offer_ids:
            raise PricingRouteViolation("pricing candidates require unique offer_id values")
        offer_ids.append(offer_id)
        if "score" in item:
            scores[offer_id] = item.get("score")
    return offer_ids, scores


def handle_pricing_select(
    payload: dict[str, Any], effects: EffectsPort, env: Any, *, selection_service: Any,
    catalog_resolver: Any | None = None,
) -> Any:
    body = dict(payload or {})
    try:
        route = extract_strict_route_from_envelope(payload=body, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = best_effort_route_ids(payload=body, env=env)
        return _blocked_message(payload=body, effects=effects, decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id, text=safe_route_blocked_text("Pricing"), reason="route_violation", exc=exc)
    if selection_service is None:
        raise RuntimeError("boot failure: pricing selection_service must be wired before handler dispatch")

    try:
        tenant_id = str(body.get("tenant_id") or "").strip()
        product_id = str(body.get("product_id") or "").strip()
        user_id = str(body.get("user_id") or "").strip()
        if not tenant_id:
            raise PricingRouteViolation("tenant_id is required")
        if not product_id:
            raise PricingRouteViolation("product_id is required")
        if not user_id:
            raise PricingRouteViolation("user_id is required")

        evidence = dict(body.get("evidence") or {})
        raw_environment = evidence.get("environment", "prod")
        if not isinstance(raw_environment, str) or not raw_environment.strip():
            raise PricingRouteViolation("evidence.environment must be a non-empty string")
        environment = raw_environment.strip()
        variant = evidence.get("variant", "a")
        if not isinstance(variant, str) or not variant.strip():
            raise PricingRouteViolation("evidence.variant must be a non-empty string")
        context = PricingSelectionContext(tenant_id=tenant_id, decision_id=route.decision_id,
            correlation_id=route.correlation_id, issuer_id=route.issuer_id, action=route.action)
        resolver = catalog_resolver or OfferCatalogResolver()
        catalog = resolver.resolve_from_product(product={"product_id": product_id, "environment": environment},
            tenant_id=tenant_id, context={"environment": environment})

        requested_offer_ids, legacy_scores = _legacy_shortlist(body.get("candidates"))
        if "candidate_scores" not in evidence:
            evidence["candidate_scores"] = legacy_scores
        selection_result = selection_service.select_from_catalog(
            ctx=context, catalog=catalog, evidence=evidence,
            evidence_score=evidence.get("evidence_score", 0.0), candidate_offer_ids=requested_offer_ids,
            completed_offer_ids=evidence.get("completed_offer_ids", ()),
            min_price_rub=evidence.get("min_price_rub", 0), max_price_rub=evidence.get("max_price_rub"),
        )
        selected = selection_result.get("selected") if isinstance(selection_result, Mapping) else None
        selected_offer = dict(selected) if isinstance(selected, Mapping) else {}
        if not selected_offer:
            raise PricingRouteViolation("no selectable pricing candidate")

        rendered = catalog.render(offer_id=str(selected_offer.get("offer_id") or ""), user_id=user_id,
            price_rub=int(selected_offer.get("price_rub") or 0), variant=variant.strip(),
            context={"tenant_id": tenant_id, "product_id": product_id, "environment": environment})
        text = str(rendered.text or selected_offer.get("title") or "💸 Pricing proposal selected")
        delivery = effects.send_message(
            decision_id=route.decision_id, correlation_id=route.correlation_id, tenant_id=tenant_id, user_id=user_id,
            text=text, track_event_type=ACTION_NAME,
            track_payload={"tenant_id": tenant_id, "product_id": product_id, "catalog_id": str(catalog.id),
                "offer_id": str(selected_offer.get("offer_id") or ""),
                "price_rub": int(selected_offer.get("price_rub") or 0), "selected": True},
            **delivery_kwargs(body),
        )
        router_evidence = _delivery_evidence(delivery)
        delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
        verified = bool(delivery_ok and router_evidence)
        return {"ok": verified, "status": "verified" if verified else "failed", "selection": selected_offer,
            "selection_result": {**dict(selection_result), "catalog_id": str(catalog.id)}, "delivery": delivery,
            "router_evidence": router_evidence if verified else None}
    except (ValueError, KeyError) as exc:
        return _blocked_message(payload=body, effects=effects, decision_id=route.decision_id,
            correlation_id=route.correlation_id, text=safe_route_blocked_text("Pricing"),
            reason="pricing_route_violation", exc=exc)
