"""Operator param resolution and policy rails. No impulse/apply logic."""

from __future__ import annotations

from typing import Any, Mapping

from core.behavior.dirac_operator_keys import required_operator_keys
from core.behavior.operator_catalogs import OperatorCatalogKey, OperatorCatalogResolver
from core.behavior.operator_policy_catalogs import OperatorPolicyCatalogResolver, OperatorPolicyContext
from core.observability.silent import swallow
from core.tenancy.normalization import normalize_tenant_id


def resolve_operator_params(ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve effective operator params from catalog + overrides."""
    from core.behavior.dirac_operator_math import clamp

    catalog_id = str(ctx.get("operator_catalog_id") or "default").strip() or "default"
    tenant_id = normalize_tenant_id(ctx.get("tenant_id"))
    product_id = str(ctx.get("product_id") or "").strip()
    domain = str(ctx.get("domain") or "").strip()
    environment = str(ctx.get("environment") or "prod").strip() or "prod"

    resolver = OperatorCatalogResolver()
    cat = resolver.resolve(
        key=OperatorCatalogKey(
            tenant_id=tenant_id,
            product_id=product_id,
            domain=domain,
            environment=environment,
        ),
        fallback_catalog_id=catalog_id,
    )

    overrides = ctx.get("operator_overrides")
    ov = dict(overrides) if isinstance(overrides, Mapping) else {}

    phase_gain = clamp(float(ov.get("phase_gain", cat.phase_gain)), 0.0, 0.5)
    k_tp = clamp(float(ov.get("k_tp", cat.k_tp)), 0.0, 0.20)
    k_vp = clamp(float(ov.get("k_vp", cat.k_vp)), 0.0, 0.20)
    k_it = clamp(float(ov.get("k_it", cat.k_it)), 0.0, 0.20)
    anti_drain = clamp(float(ov.get("anti_drain", cat.anti_drain)), 0.0, 0.35)

    es: dict[str, float] = dict(getattr(cat, "event_scales", {}) or {})
    ov_es = ov.get("event_scales")
    if isinstance(ov_es, Mapping):
        for k, v in dict(ov_es).items():
            kk = str(k or "").strip().lower()
            if kk:
                es[kk] = float(clamp(float(v), 0.25, 3.0))

    return {
        "catalog": cat,
        "phase_gain": phase_gain,
        "k_tp": k_tp,
        "k_vp": k_vp,
        "k_it": k_it,
        "anti_drain": anti_drain,
        "event_scales": es,
        "domain": domain,
    }


def policy_ctx_from_context(ctx: Mapping[str, Any]) -> OperatorPolicyContext:
    raw = ctx.get("policy_context")
    if isinstance(raw, Mapping):
        return OperatorPolicyContext(
            funnel_stage=str(raw.get("funnel_stage")) if raw.get("funnel_stage") else None,
            actor_role=str(raw.get("actor_role")) if raw.get("actor_role") else None,
        )
    fs = ctx.get("funnel_stage")
    ar = ctx.get("actor_role")
    return OperatorPolicyContext(
        funnel_stage=str(fs) if fs else None,
        actor_role=str(ar) if ar else None,
    )


def is_operator_allowed(*, event_type: str, ctx: Mapping[str, Any]) -> bool:
    policy_ref = ctx.get("operator_policy_catalog_ref")
    pol_ctx = policy_ctx_from_context(ctx)

    if not policy_ref and not (pol_ctx.funnel_stage or pol_ctx.actor_role):
        return True

    try:
        resolver = OperatorPolicyCatalogResolver()
        catalog = resolver.resolve(
            catalog_ref=str(policy_ref) if policy_ref else None,
            tenant_id=normalize_tenant_id(ctx.get("tenant_id")),
            product_id=str(ctx.get("product_id") or "") or None,
            env=str(ctx.get("environment") or "prod"),
        )
        catalog.validate_operator_keys(required_operator_keys())
        allowed = bool(catalog.is_allowed(str(event_type), ctx=pol_ctx))

        if not allowed:
            den = ctx.get("policy_denials")
            if isinstance(den, dict):
                k = str(event_type)
                den[k] = int(den.get(k, 0)) + 1
            try:
                if isinstance(ctx, dict) and bool(ctx.get("safe_mode")):
                    ctx["guardrails_violation"] = True
            except Exception:
                swallow(__name__, "core/behavior/dirac_operator_params")

        return allowed
    except Exception:
        return True


__all__ = ["resolve_operator_params", "policy_ctx_from_context", "is_operator_allowed"]
