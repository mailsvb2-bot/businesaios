from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from runtime.actions import ACTION_PRICING_SELECT_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.execution.governance_runtime_support import _build_default_approval_execution_gate
from runtime.handler_impl.core.payloads import required_str
from runtime.handlers.delivery_contract import delivery_kwargs
from runtime.handlers.platform_effects import _trusted_delivery_evidence
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.messaging_policy.discipline import ensure_policy_input_disciplined
from runtime.messaging_preferences.load_preference import load_channel_preference
from runtime.ports.effects import EffectsPort
from runtime.pricing import OfferCatalogKey, OfferCatalogResolver
from runtime.pricing import PricingRouteViolation, PricingSelectionContext
CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_PRICING_SELECT_V1


def _blocked(payload, effects, decision_id, correlation_id, reason, exc) -> dict[str, Any]:
    delivery = effects.send_message(decision_id=decision_id, correlation_id=correlation_id, tenant_id=str(payload.get("tenant_id") or "").strip(), user_id=str(payload.get("user_id") or ""), text=safe_route_blocked_text("Pricing"), track_event_type="pricing_select_blocked@v1", track_payload=blocked_error_payload(reason=reason, exc=exc), **delivery_kwargs(payload))
    return {"ok": False, "status": "blocked", "reason": reason, "delivery": delivery, "router_evidence": None}


def _shortlist(raw: object) -> tuple[list[str] | None, dict[str, object]]:
    if raw is None:
        return None, {}
    if not isinstance(raw, list):
        raise PricingRouteViolation("candidates must be a list")
    ids, scores = [], {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise PricingRouteViolation("pricing candidate must be an object")
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id or offer_id in ids:
            raise PricingRouteViolation("pricing candidates require unique offer_id values")
        ids.append(offer_id)
        if "score" in item:
            scores[offer_id] = item.get("score")
    return ids, scores


def _approval_review(*, selected, catalog_id, tenant_id, product_id, user_id, environment, variant, text, delivery, preference, route, evidence, approval_gate):
    approval_id = evidence.get("approval_id")
    if approval_id is not None and (not isinstance(approval_id, str) or not approval_id.strip()):
        raise PricingRouteViolation("evidence.approval_id must be a non-empty string")
    subject = {"user_id": user_id, "product_id": product_id, "catalog_id": catalog_id, "offer_id": str(selected.get("offer_id") or ""), "price_rub": int(selected.get("price_rub") or 0), "environment": environment, "variant": variant, "content_sha256": sha256(text.encode()).hexdigest(), "delivery": dict(delivery), "preference_snapshot": {"primary": preference.primary, "enabled": list(preference.enabled), "verified": list(preference.verified)}}
    ctx = ActionExecutionContext(tenant_id=tenant_id, user_id=user_id, action_name=ACTION_NAME, payload=subject, metadata={"decision_id": route.decision_id, "correlation_id": route.correlation_id, "tags": ["pricing", "offer_approval"]}, execution_id=route.decision_id)
    impact = ActionImpact(action_name=ACTION_NAME, category=ActionCategory.OUTBOUND, outbound_count=1, requires_human_approval=True, confidence=1.0)
    verdict = (approval_gate or _build_default_approval_execution_gate()).evaluate(ctx=ctx, impact=impact, external_confirmation_mode="required", approval_policy={"force_human_approval": True}, metadata={"decision_id": route.decision_id, "requires_manual_review": True, "tags": ["pricing", "offer_approval"]}, approval_id=approval_id.strip() if isinstance(approval_id, str) else None, requested_by=user_id)
    return None if verdict.allowed else {"ok": False, "status": "approval_required", "reason": str(verdict.reason), "approval": verdict.to_dict(), "selection": dict(selected), "delivery": None, "router_evidence": None}


def _transport_guard(settings_gateway, tenant_id, approved):
    return lambda _msg: "" if load_channel_preference(settings_gateway=settings_gateway, tenant_id=tenant_id) == approved else "preference_changed"


def handle_pricing_select(payload: dict[str, Any], effects: EffectsPort, env: Any, *, selection_service: Any, catalog_resolver: Any | None = None, approval_gate: Any | None = None, settings_gateway: Any | None = None) -> Any:
    body = dict(payload or {})
    try:
        route = extract_strict_route_from_envelope(payload=body, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        decision_id, correlation_id = best_effort_route_ids(payload=body, env=env)
        return _blocked(body, effects, decision_id, correlation_id, "route_violation", exc)
    if selection_service is None:
        raise RuntimeError("boot failure: pricing selection_service must be wired before handler dispatch")
    try:
        tenant_id, product_id, user_id = (required_str(body, key) for key in ("tenant_id", "product_id", "user_id"))
        evidence = dict(body.get("evidence") or {})
        environment, variant = evidence.get("environment", "prod"), evidence.get("variant", "a")
        if not isinstance(environment, str) or not environment.strip():
            raise PricingRouteViolation("evidence.environment must be a non-empty string")
        if not isinstance(variant, str) or not variant.strip():
            raise PricingRouteViolation("evidence.variant must be a non-empty string")
        environment, variant = environment.strip(), variant.strip()
        effective = delivery_kwargs(body)
        policy = effective.get("channel_policy")
        effective["channel_policy"] = ensure_policy_input_disciplined(policy) if isinstance(policy, Mapping) and policy else None
        context = PricingSelectionContext(tenant_id=tenant_id, decision_id=route.decision_id, correlation_id=route.correlation_id, issuer_id=route.issuer_id, action=route.action)
        catalog = (catalog_resolver or OfferCatalogResolver()).resolve(key=OfferCatalogKey(tenant_id=tenant_id, product_id=product_id, environment=environment))
        requested, legacy_scores = _shortlist(body.get("candidates"))
        evidence.setdefault("candidate_scores", legacy_scores)
        result = selection_service.select_from_catalog(ctx=context, catalog=catalog, evidence=evidence, evidence_score=evidence.get("evidence_score", 0.0), candidate_offer_ids=requested, completed_offer_ids=evidence.get("completed_offer_ids", ()), min_price_rub=evidence.get("min_price_rub", 0), max_price_rub=evidence.get("max_price_rub"))
        selected = result.get("selected") if isinstance(result, Mapping) else None
        selected = dict(selected) if isinstance(selected, Mapping) else {}
        if not selected:
            raise PricingRouteViolation("no selectable pricing candidate")
        rendered = catalog.render(offer_id=str(selected.get("offer_id") or ""), user_id=user_id, price_rub=int(selected.get("price_rub") or 0), variant=variant, context={"tenant_id": tenant_id, "product_id": product_id, "environment": environment})
        text = str(rendered.text or selected.get("title") or "💸 Pricing proposal selected")
        commercial = selected.get("commercial")
        needs_approval = isinstance(commercial, Mapping) and commercial.get("requires_human_approval") is True
        preference = load_channel_preference(settings_gateway=settings_gateway, tenant_id=tenant_id) if needs_approval else None
        approval = _approval_review(selected=selected, catalog_id=str(catalog.id), tenant_id=tenant_id, product_id=product_id, user_id=user_id, environment=environment, variant=variant, text=text, delivery=effective, preference=preference, route=route, evidence=evidence, approval_gate=approval_gate) if preference is not None else None
        selection_result = {**dict(result), "catalog_id": str(catalog.id)}
        if approval is not None:
            return {**approval, "selection_result": selection_result}
        delivery = effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, tenant_id=tenant_id, user_id=user_id, text=text, track_event_type=ACTION_NAME, track_payload={"tenant_id": tenant_id, "product_id": product_id, "catalog_id": str(catalog.id), "offer_id": str(selected.get("offer_id") or ""), "price_rub": int(selected.get("price_rub") or 0), "selected": True}, transport_guard=_transport_guard(settings_gateway, tenant_id, preference) if preference is not None else None, **effective)
        router_evidence = _trusted_delivery_evidence(delivery)
        ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
        verified = bool(ok and router_evidence)
        return {"ok": verified, "status": "verified" if verified else "failed", "selection": selected, "selection_result": selection_result, "delivery": delivery, "router_evidence": router_evidence if verified else None}
    except (PricingRouteViolation, ValueError, KeyError) as exc:
        return _blocked(body, effects, route.decision_id, route.correlation_id, "pricing_route_violation", exc)
