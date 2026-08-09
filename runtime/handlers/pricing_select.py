from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from core.offers.offer_catalog_resolver import OfferCatalogKey, OfferCatalogResolver
from runtime.actions import ACTION_PRICING_SELECT_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.execution.governance_runtime_support import build_default_approval_execution_gate
from runtime.handlers.delivery_contract import delivery_kwargs
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.messaging_policy.discipline import ensure_policy_input_disciplined
from runtime.messaging_preferences.load_preference import load_channel_preference
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


def _effective_delivery(payload: Mapping[str, Any]) -> dict[str, Any]:
    effective = delivery_kwargs(payload)
    policy = effective.get("channel_policy")
    if not isinstance(policy, Mapping) or not policy:
        effective["channel_policy"] = None
        return effective
    effective["channel_policy"] = ensure_policy_input_disciplined(policy)
    return effective


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


def _approval_id(evidence: Mapping[str, object]) -> str | None:
    raw = evidence.get("approval_id")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise PricingRouteViolation("evidence.approval_id must be a non-empty string")
    return raw.strip()


def _requires_human_approval(selected_offer: Mapping[str, object]) -> bool:
    commercial = selected_offer.get("commercial")
    return bool(isinstance(commercial, Mapping) and commercial.get("requires_human_approval") is True)


def _review_selected_offer(
    *, selected_offer: Mapping[str, object], catalog_id: str, tenant_id: str, product_id: str,
    user_id: str, environment: str, variant: str, content_sha256: str, effective_delivery: Mapping[str, Any],
    preference_snapshot: Mapping[str, object] | None, route: Any, evidence: Mapping[str, object], approval_gate: Any | None,
) -> dict[str, Any] | None:
    if not _requires_human_approval(selected_offer):
        return None
    gate = approval_gate or build_default_approval_execution_gate()
    approval_id = _approval_id(evidence)
    subject = {
        "user_id": user_id,
        "product_id": product_id,
        "catalog_id": catalog_id,
        "offer_id": str(selected_offer.get("offer_id") or ""),
        "price_rub": int(selected_offer.get("price_rub") or 0),
        "environment": environment,
        "variant": variant,
        "content_sha256": content_sha256,
        "delivery": dict(effective_delivery),
        "preference_snapshot": dict(preference_snapshot or {}),
    }
    ctx = ActionExecutionContext(
        tenant_id=tenant_id, user_id=user_id, action_name=ACTION_NAME, payload=subject,
        metadata={"decision_id": route.decision_id, "correlation_id": route.correlation_id, "tags": ["pricing", "offer_approval"]},
        execution_id=route.decision_id,
    )
    impact = ActionImpact(
        action_name=ACTION_NAME, category=ActionCategory.OUTBOUND, outbound_count=1,
        requires_human_approval=True, confidence=1.0,
    )
    verdict = gate.evaluate(
        ctx=ctx, impact=impact, external_confirmation_mode="required",
        approval_policy={"force_human_approval": True},
        metadata={"decision_id": route.decision_id, "requires_manual_review": True, "tags": ["pricing", "offer_approval"]},
        approval_id=approval_id, requested_by=user_id,
    )
    if verdict.allowed:
        return None
    return {
        "ok": False,
        "status": "approval_required",
        "reason": str(verdict.reason),
        "approval": verdict.to_dict(),
        "selection": dict(selected_offer),
        "delivery": None,
        "router_evidence": None,
    }


def _approval_transport_guard(*, settings_gateway: Any | None, tenant_id: str, approved_preference: Any):
    def _guard(_msg) -> str:
        current = load_channel_preference(settings_gateway=settings_gateway, tenant_id=tenant_id)
        return "" if current == approved_preference else "preference_changed"

    return _guard


def handle_pricing_select(
    payload: dict[str, Any], effects: EffectsPort, env: Any, *, selection_service: Any,
    catalog_resolver: Any | None = None, approval_gate: Any | None = None, settings_gateway: Any | None = None,
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
        variant = variant.strip()
        effective_delivery = _effective_delivery(body)
        context = PricingSelectionContext(tenant_id=tenant_id, decision_id=route.decision_id,
            correlation_id=route.correlation_id, issuer_id=route.issuer_id, action=route.action)
        resolver = catalog_resolver or OfferCatalogResolver()
        catalog = resolver.resolve(key=OfferCatalogKey(tenant_id=tenant_id, product_id=product_id, environment=environment))

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
            price_rub=int(selected_offer.get("price_rub") or 0), variant=variant,
            context={"tenant_id": tenant_id, "product_id": product_id, "environment": environment})
        text = str(rendered.text or selected_offer.get("title") or "💸 Pricing proposal selected")
        requires_approval = _requires_human_approval(selected_offer)
        approved_preference = (
            load_channel_preference(settings_gateway=settings_gateway, tenant_id=tenant_id)
            if requires_approval else None
        )
        approval_result = _review_selected_offer(
            selected_offer=selected_offer, catalog_id=str(catalog.id), tenant_id=tenant_id, product_id=product_id,
            user_id=user_id, environment=environment, variant=variant,
            content_sha256=sha256(text.encode("utf-8")).hexdigest(), effective_delivery=effective_delivery,
            preference_snapshot=None if approved_preference is None else approved_preference.to_mapping(),
            route=route, evidence=evidence, approval_gate=approval_gate,
        )
        if approval_result is not None:
            return {**approval_result, "selection_result": {**dict(selection_result), "catalog_id": str(catalog.id)}}

        transport_guard = (
            _approval_transport_guard(settings_gateway=settings_gateway, tenant_id=tenant_id, approved_preference=approved_preference)
            if approved_preference is not None else None
        )
        delivery = effects.send_message(
            decision_id=route.decision_id, correlation_id=route.correlation_id, tenant_id=tenant_id, user_id=user_id,
            text=text, track_event_type=ACTION_NAME,
            track_payload={"tenant_id": tenant_id, "product_id": product_id, "catalog_id": str(catalog.id),
                "offer_id": str(selected_offer.get("offer_id") or ""),
                "price_rub": int(selected_offer.get("price_rub") or 0), "selected": True},
            transport_guard=transport_guard, **effective_delivery,
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
