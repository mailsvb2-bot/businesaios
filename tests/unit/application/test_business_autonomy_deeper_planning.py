import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    IntegrationMode,
    PolicyConstraint,
)
from application.planning.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from tests.support.business_autonomy import build_explicitly_onboarded_service


@pytest.mark.asyncio
async def test_business_autonomy_publishes_multi_goal_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_explicitly_onboarded_service(tenant_id="tenant-a", business_id="sample_business")
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="sample_business",
            goal_id="goal-x",
            goal_type="grow_revenue",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            simulation=True,
            constraints=(PolicyConstraint(name="monthly_budget_limit", value=10.0),),
            metadata={"tenant_id": "tenant-a", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="corr-x",
        idempotency_key="idem-x",
    )
    result = await service.execute(request)
    assert result.verdict.value == "simulated"

    store = FileMultiGoalPlannerStore(root_dir=tmp_path / "runtime" / "planning_memory" / "multi_goal")
    planner = MultiGoalPlannerService(store=store)
    context = planner.load_context(tenant_id="tenant-a", business_id="sample_business")
    goal_ids = {str(item.get("goal_id") or "") for item in context.get("queue", [])}
    assert "goal-x" in goal_ids
