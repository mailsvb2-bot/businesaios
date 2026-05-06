from __future__ import annotations

from pathlib import Path

from core.behavior.math.complex4 import Complex4
from core.behavior.operator_catalogs.operator_catalog_resolver import (
    OperatorCatalogKey,
    OperatorCatalogResolver,
)
from core.behavior.operator_catalogs.registry import OperatorCatalogRegistry
from core.behavior.operator_policy_catalogs.evaluator import is_operator_allowed
from core.behavior.operator_policy_catalogs.registry import OperatorPolicyCatalogRegistry
from core.behavior.operators.operator_application import apply_operator
from core.behavior.operators.operator_denials import PolicyDenials
from core.behavior.operators.operator_runtime_context import OperatorRuntimeContext
from core.tenancy.normalization import normalize_tenant_id


class DiracOperatorService:
    def __init__(self, catalog_root: Path, policy_root: Path) -> None:
        registry = OperatorCatalogRegistry(base_dir=catalog_root)
        self._catalog_resolver = OperatorCatalogResolver(catalogs=registry)
        self._policy_registry = OperatorPolicyCatalogRegistry(policy_root)

    def apply(self, psi: Complex4, operator_key: str, ctx: OperatorRuntimeContext, denials: PolicyDenials) -> Complex4:
        policy = self._policy_registry.get(ctx.operator_policy_catalog_ref or "") if ctx.operator_policy_catalog_ref else None
        if not is_operator_allowed(policy, operator_key, funnel_stage=ctx.funnel_stage, actor_role=ctx.actor_role):
            denials.add(operator_key, safe_mode=ctx.safe_mode)
            return psi
        event_overrides: dict[str, tuple[float, float, float, float]] = {}
        for key, value in dict(ctx.operator_overrides or {}).items():
            if isinstance(value, (list, tuple)) and len(value) == 4:
                event_overrides[str(key)] = tuple(float(v) for v in value)
        try:
            catalog = self._catalog_resolver.resolve(
                key=OperatorCatalogKey(
                    tenant_id=normalize_tenant_id(ctx.tenant_id),
                    product_id=ctx.product or "",
                    domain=ctx.domain or "",
                    environment=ctx.env or "prod",
                ),
                fallback_catalog_id=str(ctx.operator_catalog_ref or "default").strip() or "default",
            )
        except KeyError:
            # Fail-closed to baseline operator math when catalogs are absent.
            return apply_operator(psi, operator_key, overrides=event_overrides)
        next_psi = apply_operator(psi, operator_key, overrides=event_overrides)
        scalar = float(catalog.scale_for(event_type=operator_key, domain=ctx.domain or ""))
        scalar = max(0.8, min(1.2, scalar))
        next_psi = next_psi.scale(scalar).renormalize()
        if catalog.anti_drain > 0.0:
            drained = list(next_psi.re)
            drained[1] = min(1.0, drained[1] + catalog.anti_drain)
            next_psi = Complex4(tuple(drained), next_psi.im).renormalize()
        return next_psi
