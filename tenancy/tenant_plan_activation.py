from __future__ import annotations

from dataclasses import dataclass

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPlan, TenantRecord
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_registry import InMemoryTenantRegistry


CANON_TENANT_PLAN_ACTIVATION = True


@dataclass(frozen=True)
class TenantPlanActivationResult:
    record: TenantRecord
    policy: TenantPolicyBundle
    changed: bool


class TenantPlanActivationService:
    """Coordinate canonical registry/policy owners; never resolve entitlements here."""

    def __init__(self, *, tenant_registry: InMemoryTenantRegistry, tenant_policy_store: InMemoryTenantPolicyStore) -> None:
        self._tenant_registry = tenant_registry
        self._tenant_policy_store = tenant_policy_store

    def activate(self, *, tenant_id: str, plan: TenantPlan, policy: TenantPolicyBundle) -> TenantPlanActivationResult:
        tid = require_tenant_id(tenant_id)
        target_plan = plan if isinstance(plan, TenantPlan) else TenantPlan(str(plan))
        policy.validate()
        if require_tenant_id(policy.tenant_id) != tid:
            raise ValueError("cross-tenant plan activation is forbidden")

        previous_record = self._tenant_registry.require(tid)
        previous_policy = self._tenant_policy_store.require(tid)
        if previous_record.plan is target_plan and previous_policy == policy:
            return TenantPlanActivationResult(previous_record, previous_policy, False)

        try:
            # Persist rights first so a crash never advertises a paid plan with stale rights.
            saved_policy = self._tenant_policy_store.save(policy)
            saved_record = self._tenant_registry.set_plan(tenant_id=tid, plan=target_plan)
        except Exception as exc:
            rollback_errors: list[Exception] = []
            restorers = (
                lambda: self._tenant_registry.set_plan(tenant_id=tid, plan=previous_record.plan),
                lambda: self._tenant_policy_store.save(previous_policy),
            )
            for restore in restorers:
                try:
                    restore()
                except Exception as rollback_exc:  # pragma: no cover - catastrophic storage failure
                    rollback_errors.append(rollback_exc)
            if rollback_errors:
                raise RuntimeError("tenant plan activation failed and rollback was incomplete") from exc
            raise
        return TenantPlanActivationResult(saved_record, saved_policy, True)
