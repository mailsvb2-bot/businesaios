from __future__ import annotations

import json

import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
    PolicyConstraint,
)
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


pytestmark = pytest.mark.asyncio


def _request(
    *,
    tenant_id: str = "tenant-safety",
    business_id: str = "site-safety",
    goal_id: str = "goal-safety",
    estimated_cost: float = 1.0,
    outbound_count: int = 1,
    constraints: tuple[PolicyConstraint, ...] = (),
    metadata: dict[str, object] | None = None,
    idempotency_key: str = "idem-safety",
) -> BusinessExecutionRequest:
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id=business_id,
            goal_id=goal_id,
            goal_type="paid_campaign_launch",
            goal_payload={"estimated_cost": estimated_cost, "outbound_count": outbound_count},
            constraints=constraints,
            metadata={"tenant_id": tenant_id, "planning_horizon": "week", **dict(metadata or {})},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id=f"corr:{tenant_id}:{business_id}:{idempotency_key}",
        idempotency_key=idempotency_key,
    )


async def test_budget_safety_verdict_is_fail_closed_and_visible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-safety")

    result = await service.execute(
        _request(
            estimated_cost=125.0,
            constraints=(PolicyConstraint(name="monthly_budget_limit", value=50.0),),
            idempotency_key="budget-denied",
        )
    )

    assert result.verdict is ExecutionVerdict.REJECTED
    safety = result.metadata["safety_core"]["budget"]
    assert safety["allowed"] is False
    assert safety["reason"] == "budget_exceeded"
    assert safety["source"] == "python_safety_core"


async def test_blast_radius_safety_verdict_is_fail_closed_and_visible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-safety")

    result = await service.execute(
        _request(
            outbound_count=500,
            constraints=(PolicyConstraint(name="outbound_message_limit", value=25),),
            idempotency_key="blast-denied",
        )
    )

    assert result.verdict is ExecutionVerdict.REJECTED
    safety = result.metadata["safety_core"]["blast_radius"]
    assert safety["allowed"] is False
    assert safety["reason"] == "blast_radius_exceeded"
    assert safety["source"] == "python_safety_core"


async def test_successful_execution_persists_safety_core_verdict_in_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-safety")

    result = await service.execute(
        _request(
            estimated_cost=10.0,
            outbound_count=2,
            constraints=(
                PolicyConstraint(name="monthly_budget_limit", value=50.0),
                PolicyConstraint(name="outbound_message_limit", value=25),
                PolicyConstraint(name="require_human_approval", value=True),
            ),
            metadata={"approved_by": "operator-1"},
            idempotency_key="safety-visible",
        )
    )

    assert result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED}
    assert result.metadata["safety_core"]["budget"]["allowed"] is True
    assert result.metadata["safety_core"]["blast_radius"]["allowed"] is True

    artifact_path = tmp_path / "runtime" / "business_autonomy" / f"{result.execution_id}.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metadata"]["safety_core"]["budget"]["reason"] == "allow"
    assert artifact["metadata"]["safety_core"]["blast_radius"]["reason"] == "allow"
