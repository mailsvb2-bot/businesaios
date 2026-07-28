import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    IntegrationMode,
    PolicyConstraint,
)
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from tests.support.business_autonomy import (
    approve_pending_and_execute,
    build_explicitly_onboarded_service,
)


def test_persistent_capability_and_trust_registries_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _ = build_business_autonomy_guarded_service(business_id="demo-biz", seed_admin_read_model=True)
    handlers = build_business_autonomy_route_handlers()
    caps = handlers.get_registered_capabilities("demo-biz")
    trust = handlers.get_trust_profile("demo-biz")
    assert caps["business_id"] == "demo-biz"
    assert len(caps["capabilities"]) >= 1
    assert trust["trust_tier"] in {"high", "critical", "medium", "low", "unknown"}


@pytest.mark.asyncio
async def test_business_autonomy_records_planning_memory_and_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_explicitly_onboarded_service(tenant_id="tenant-a", business_id="demo-biz")
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="demo-biz",
            goal_id="goal-1",
            goal_type="deliver_session",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            simulation=True,
            constraints=(
                PolicyConstraint(name="monthly_budget_limit", value=10.0),
                PolicyConstraint(name="require_human_approval", value=True),
            ),
            metadata={"tenant_id": "tenant-a", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="corr-1",
        idempotency_key="idem-1",
    )
    result = await approve_pending_and_execute(service, request)
    assert result.verdict.value == "simulated"
