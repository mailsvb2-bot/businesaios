from __future__ import annotations

from billing.plan_contract import TenantPlanStoreContract
from tenancy.tenant_contract import TenantPlan


def test_plan_store_protocol_is_contract_only_without_hidden_runtime() -> None:
    marker = object()

    assert TenantPlanStoreContract.get_binding(marker, "tenant-a") is None
    assert TenantPlanStoreContract.save_binding(marker, object()) is None
    assert TenantPlanStoreContract.get_plan(marker, "tenant-a") is None
    assert TenantPlanStoreContract.get_plan_by_id(marker, TenantPlan.GROWTH) is None
    assert TenantPlanStoreContract.save_plan(marker, object()) is None
