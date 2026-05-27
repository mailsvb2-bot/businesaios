import pytest

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode
from application.planning.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


@pytest.mark.asyncio
async def test_business_autonomy_publishes_multi_goal_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="metrotherapy")
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="metrotherapy",
            goal_id="goal-x",
            goal_type="grow_revenue",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            metadata={"tenant_id": "tenant-a", "approved_by": "operator-1", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="corr-x",
        idempotency_key="idem-x",
    )
    result = await service.execute(request)
    assert result.verdict.value in {"completed", "simulated"}

    store = FileMultiGoalPlannerStore(root_dir=tmp_path / "runtime" / "planning_memory" / "multi_goal")
    planner = MultiGoalPlannerService(store=store)
    context = planner.load_context(tenant_id="tenant-a", business_id="metrotherapy")
    goal_ids = {str(item.get("goal_id") or "") for item in context.get("queue", [])}
    assert "goal-x" in goal_ids
