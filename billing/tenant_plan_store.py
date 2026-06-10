from __future__ import annotations

from dataclasses import replace

from billing.plan_contract import BillingPlanBinding, BillingPlanSpec, TenantPlanStoreContract
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPlan

CANON_TENANT_PLAN_STORE = True


class InMemoryTenantPlanStore(TenantPlanStoreContract):
    """Commercial plan registry.

    Owns only passive plan metadata and tenant bindings.
    It does not own execution, pricing decisions, or routing.
    """

    def __init__(self) -> None:
        self._plans: dict[TenantPlan, BillingPlanSpec] = {}
        self._bindings: dict[str, BillingPlanBinding] = {}

    def get_binding(self, tenant_id: str) -> BillingPlanBinding | None:
        current = self._bindings.get(require_tenant_id(tenant_id))
        return None if current is None else replace(current, overrides=dict(current.overrides))

    def list_bindings(self) -> tuple[BillingPlanBinding, ...]:
        return tuple(self.get_binding(tenant_id) for tenant_id in sorted(self._bindings))

    def save_binding(self, binding: BillingPlanBinding) -> BillingPlanBinding:
        normalized = binding.normalized_copy()
        self._bindings[normalized.tenant_id] = normalized
        return self.get_binding(normalized.tenant_id)  # type: ignore[return-value]

    def unbind(self, tenant_id: str) -> None:
        self._bindings.pop(require_tenant_id(tenant_id), None)

    def get_plan(self, tenant_id: str) -> BillingPlanSpec | None:
        binding = self.get_binding(tenant_id)
        if binding is None:
            return None
        return self.get_plan_by_id(binding.plan_id)

    def save_plan(self, plan: BillingPlanSpec) -> BillingPlanSpec:
        normalized = plan.normalized_copy()
        self._plans[normalized.plan_id] = normalized
        return self.get_plan_by_id(normalized.plan_id)  # type: ignore[return-value]

    def get_plan_by_id(self, plan_id: TenantPlan) -> BillingPlanSpec | None:
        current = self._plans.get(plan_id)
        return None if current is None else current.normalized_copy()

    def list_plans(self) -> tuple[BillingPlanSpec, ...]:
        return tuple(self.get_plan_by_id(plan_id) for plan_id in TenantPlan if self.get_plan_by_id(plan_id) is not None)

    def require_plan(self, tenant_id: str) -> BillingPlanSpec:
        plan = self.get_plan(tenant_id)
        if plan is None:
            raise KeyError(f"missing plan binding or plan spec for tenant: {tenant_id}")
        return plan

    def bind(self, *, tenant_id: str, plan_id: TenantPlan) -> BillingPlanBinding:
        return self.save_binding(BillingPlanBinding(tenant_id=require_tenant_id(tenant_id), plan_id=plan_id))


__all__ = [
    "CANON_TENANT_PLAN_STORE",
    "InMemoryTenantPlanStore",
    "TenantPlanStoreContract",
]
