from dataclasses import replace

import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    IntegrationMode,
    PolicyConstraint,
)
from tenancy.tenant_policy_store import (
    build_default_tenant_policy_bundle,
    build_default_tenant_policy_store,
)
from tests.support.business_autonomy import build_explicitly_onboarded_service


@pytest.mark.asyncio
async def test_business_autonomy_guarded_service_uses_persistent_backends(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_explicitly_onboarded_service(
        tenant_id="tenant-a",
        business_id="external_business",
    )
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="external_business",
            goal_id="g1",
            goal_type="deliver_value",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            simulation=True,
            constraints=(PolicyConstraint(name="monthly_budget_limit", value=10.0),),
            metadata={"tenant_id": "tenant-a"},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="c1",
        idempotency_key="idem-1",
    )
    result = await service.execute(request)
    assert result.verdict.value == "simulated"

@pytest.mark.asyncio
async def test_business_autonomy_scope_materializes_quota_policy_without_overwriting_existing_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    policy_store = build_default_tenant_policy_store()
    custom = build_default_tenant_policy_bundle("tenant-quota")
    policy_store.save(
        replace(
            custom,
            quotas={**dict(custom.quotas), "connector_calls_per_hour": 3.0},
        )
    )

    service = build_explicitly_onboarded_service(
        tenant_id="tenant-quota",
        business_id="quota-business",
    )
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="quota-business",
            goal_id="quota-goal",
            goal_type="deliver_value",
            goal_payload={"estimated_cost": 1.0},
            simulation=True,
            constraints=(PolicyConstraint(name="monthly_budget_limit", value=10.0),),
            metadata={"tenant_id": "tenant-quota"},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="quota-corr",
        idempotency_key="quota-idem",
    )

    result = await service.execute(request)
    assert result.verdict.value == "simulated"

    reloaded = build_default_tenant_policy_store().require("tenant-quota")
    assert reloaded.quotas["connector_calls_per_hour"] == 3.0

