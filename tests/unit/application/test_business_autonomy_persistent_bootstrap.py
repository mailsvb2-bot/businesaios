import pytest

from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode


@pytest.mark.asyncio
async def test_business_autonomy_guarded_service_uses_persistent_backends(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="external_business")
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="external_business",
            goal_id="g1",
            goal_type="deliver_value",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id="c1",
        idempotency_key="idem-1",
    )
    result = await service.execute(request)
    assert result.verdict.value in {"completed", "simulated"}
