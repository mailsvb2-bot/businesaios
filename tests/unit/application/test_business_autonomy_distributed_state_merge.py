from __future__ import annotations

import json

import pytest

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


@pytest.mark.asyncio
async def test_business_autonomy_distributed_documents_merge_across_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-biz")

    first = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="site-biz",
            goal_id="goal-1",
            goal_type="publish",
            goal_payload={"estimated_cost": 1.0, "outbound_count": 1},
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
            metadata={"tenant_id": "tenant-a", "planning_horizon": "week"},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        idempotency_key="idem-2",
    )

    await service.execute(first)
    await service.execute(second)

    registry = json.loads((tmp_path / "runtime" / "distributed" / "documents" / "business_registry.json").read_text(encoding="utf-8"))
    idem = json.loads((tmp_path / "runtime" / "distributed" / "documents" / "idempotency_records.json").read_text(encoding="utf-8"))

    assert set(registry["items"].keys()) == {"tenant-a:site-biz", "tenant-a:site-biz-2"}
    assert set(idem["items"].keys()) == {"tenant-a:site-biz:idem-1", "tenant-a:site-biz-2:idem-2"}
