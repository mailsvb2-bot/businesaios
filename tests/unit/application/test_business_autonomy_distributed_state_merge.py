from __future__ import annotations

import sqlite3

import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    IntegrationMode,
    PolicyConstraint,
)
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from tests.support.business_autonomy import explicitly_onboard_business


@pytest.mark.asyncio
async def test_business_autonomy_distributed_documents_merge_across_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    explicitly_onboard_business(tenant_id="tenant-a", business_id="site-biz")
    explicitly_onboard_business(tenant_id="tenant-a", business_id="site-biz-2")
    service = build_business_autonomy_guarded_service(business_id="site-biz")
    constraints = (
        PolicyConstraint(name="monthly_budget_limit", value=10.0),
        PolicyConstraint(name="outbound_message_limit", value=10),
    )

    first = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="site-biz",
            goal_id="goal-1",
            goal_type="publish",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            simulation=True,
            constraints=constraints,
            metadata={"tenant_id": "tenant-a", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        idempotency_key="idem-1",
    )
    second = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="site-biz-2",
            goal_id="goal-2",
            goal_type="publish",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
            simulation=True,
            constraints=constraints,
            metadata={"tenant_id": "tenant-a", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        idempotency_key="idem-2",
    )

    first_result = await service.execute(first)
    second_result = await service.execute(second)
    assert first_result.verdict.value == "simulated"
    assert second_result.verdict.value == "simulated"

    state_path = tmp_path / "runtime" / "business_autonomy_state.sqlite3"
    connection = sqlite3.connect(state_path)
    try:
        registry_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT document_id FROM distributed_documents WHERE collection = 'business_registry'"
            )
        }
        idempotency_keys = {
            str(row[0])
            for row in connection.execute(
                "SELECT record_key FROM distributed_cas WHERE scope = 'idempotency_records'"
            )
        }
    finally:
        connection.close()

    assert registry_ids == {"tenant-a:site-biz", "tenant-a:site-biz-2"}
    assert idempotency_keys == {"tenant-a:site-biz:idem-1", "tenant-a:site-biz-2:idem-2"}
