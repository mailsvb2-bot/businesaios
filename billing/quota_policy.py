from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from billing.plan_contract import TenantPlanStoreContract
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_billing_scope import BillingMode
from tenancy.tenant_contract import TenantPolicyStoreContract

CANON_QUOTA_POLICY = True


@dataclass(frozen=True)
class EffectiveQuotaPolicy:
    tenant_id: str
    plan_id: str | None
    quota_limits: Mapping[str, float] = field(default_factory=dict)
    hard_stop_dimensions: frozenset[str] = field(default_factory=frozenset)
    billing_mode: BillingMode = BillingMode.POSTPAID
    invoice_enabled: bool = True
    allow_overage: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        for key, value in self.quota_limits.items():
            if not str(key or "").strip():
                raise ValueError("quota dimension is required")
            if float(value) < 0:
                raise ValueError("quota limit must be >= 0")

    def limit_for(self, dimension: str) -> float | None:
        name = str(dimension or "").strip()
        if not name:
            raise ValueError("dimension is required")
        raw = self.quota_limits.get(name)
        return None if raw is None else float(raw)

    def hard_stop_for(self, dimension: str) -> bool:
        name = str(dimension or "").strip()
        if not name:
            raise ValueError("dimension is required")
        if self.allow_overage and name not in self.hard_stop_dimensions:
            return False
        return name in self.hard_stop_dimensions


class QuotaPolicyResolver:
    """Resolves effective commercial quota policy.

    Precedence sources:
    - plan defaults
    - binding overrides
    - tenant policy bundle

    For numeric quota ceilings, the effective limit is the strictest minimum across
    all sources that define the same dimension. This prevents plan limits from being
    silently widened by tenant-local overrides.
    """

    def __init__(
        self,
        *,
        tenant_plan_store: TenantPlanStoreContract | None = None,
        tenant_policy_store: TenantPolicyStoreContract | None = None,
    ) -> None:
        self._tenant_plan_store = tenant_plan_store
        self._tenant_policy_store = tenant_policy_store

    def resolve(self, *, tenant_id: str) -> EffectiveQuotaPolicy:
        tid = require_tenant_id(tenant_id)
        binding = None if self._tenant_plan_store is None else self._tenant_plan_store.get_binding(tid)
        plan = None if self._tenant_plan_store is None else self._tenant_plan_store.get_plan(tid)
        bundle = None if self._tenant_policy_store is None else self._tenant_policy_store.get(tid)

        limit_candidates: dict[str, list[float]] = {}
        hard_stops: set[str] = set()
        if plan is not None:
            for item in plan.quota_limits:
                normalized = item.normalized_copy()
                limit_candidates.setdefault(normalized.dimension, []).append(float(normalized.limit))
                if normalized.hard_stop:
                    hard_stops.add(normalized.dimension)

        binding_overrides = {} if binding is None else dict(binding.overrides)
        for key, value in dict(binding_overrides.get("quota_limits") or {}).items():
            limit_candidates.setdefault(str(key), []).append(float(value))

        binding_hard_stops = binding_overrides.get("hard_stop_dimensions")
        if binding_hard_stops is not None:
            hard_stops = {str(item).strip() for item in binding_hard_stops if str(item).strip()}

        if bundle is not None:
            for key, value in bundle.quotas.items():
                limit_candidates.setdefault(str(key), []).append(float(value))

        quota_limits = {dimension: min(values) for dimension, values in limit_candidates.items() if values}

        billing_scope = None if bundle is None else bundle.billing_scope
        billing_mode = BillingMode.POSTPAID if billing_scope is None else billing_scope.mode
        invoice_enabled = True if billing_scope is None else bool(billing_scope.invoice_enabled)
        allow_overage = False if billing_scope is None else bool(billing_scope.allow_overage)

        if "billing_mode" in binding_overrides:
            billing_mode = BillingMode(str(binding_overrides["billing_mode"]))
        if "invoice_enabled" in binding_overrides:
            invoice_enabled = bool(binding_overrides["invoice_enabled"])
        if "allow_overage" in binding_overrides:
            allow_overage = bool(binding_overrides["allow_overage"])

        policy = EffectiveQuotaPolicy(
            tenant_id=tid,
            plan_id=None if plan is None else plan.plan_id.value,
            quota_limits=quota_limits,
            hard_stop_dimensions=frozenset(hard_stops),
            billing_mode=billing_mode,
            invoice_enabled=invoice_enabled,
            allow_overage=allow_overage,
            metadata={
                "plan_bound": plan is not None,
                "plan_binding": None if binding is None else binding.plan_id.value,
                "binding_overrides": binding is not None and bool(binding.overrides),
                "tenant_policy_bundle": bundle is not None,
                "billing_scope_bound": billing_scope is not None,
                **({} if not isinstance(binding_overrides.get("metadata"), Mapping) else dict(binding_overrides["metadata"])),
            },
        )
        policy.validate()
        return policy


__all__ = [
    "CANON_QUOTA_POLICY",
    "EffectiveQuotaPolicy",
    "QuotaPolicyResolver",
]
