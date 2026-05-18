from __future__ import annotations

import json
from pathlib import Path

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
    tenant_id: str = "tenant-critical",
    business_id: str = "site-critical",
    goal_id: str = "goal-1",
    goal_type: str = "campaign_launch",
    estimated_cost: float = 1.0,
    outbound_count: int = 1,
    constraints: tuple[PolicyConstraint, ...] = (),
    metadata: dict[str, object] | None = None,
    idempotency_key: str = "idem-1",
) -> BusinessExecutionRequest:
    final_metadata = {"tenant_id": tenant_id, "planning_horizon": "week", **dict(metadata or {})}
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id=business_id,
            goal_id=goal_id,
            goal_type=goal_type,
            goal_payload={"estimated_cost": estimated_cost, "outbound_count": outbound_count},
            constraints=constraints,
            metadata=final_metadata,
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id=f"corr:{tenant_id}:{business_id}:{goal_id}:{idempotency_key}",
        idempotency_key=idempotency_key,
    )


def _evidence_lines(data_dir: Path) -> list[dict]:
    path = data_dir / "business_autonomy" / "evidence.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def test_money_or_live_write_requires_approval_before_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-critical")

    result = await service.execute(
        _request(
            goal_type="paid_campaign_launch",
            constraints=(PolicyConstraint(name="require_human_approval", value=True),),
        )
    )

    assert result.verdict is ExecutionVerdict.PARTIAL
    assert result.metadata["approval_status"] == "pending"
    assert _evidence_lines(tmp_path) == []


async def test_budget_guard_blocks_spend_above_limit_without_side_effects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-critical")

    result = await service.execute(
        _request(
            estimated_cost=125.0,
            constraints=(PolicyConstraint(name="monthly_budget_limit", value=50.0),),
            idempotency_key="budget-overrun",
        )
    )

    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["budget_limit"] == 50.0
    assert result.metadata["estimated_cost"] == 125.0
    assert _evidence_lines(tmp_path) == []


async def test_blast_radius_guard_blocks_ad_or_funnel_fanout_without_side_effects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-critical")

    result = await service.execute(
        _request(
            goal_type="funnel_broadcast",
            outbound_count=500,
            constraints=(PolicyConstraint(name="outbound_message_limit", value=25),),
            idempotency_key="fanout-overrun",
        )
    )

    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["outbound_limit"] == 25
    assert result.metadata["requested_outbound"] == 500
    assert _evidence_lines(tmp_path) == []


async def test_retry_or_duplicate_webhook_does_not_duplicate_evidence_or_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-critical")
    request = _request(
        goal_type="paid_campaign_launch",
        constraints=(PolicyConstraint(name="require_human_approval", value=True),),
        metadata={"approved_by": "operator-1"},
        idempotency_key="duplicate-webhook-1",
    )

    first = await service.execute(request)
    second = await service.execute(request)

    assert first.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED}
    assert second == first
    evidence = _evidence_lines(tmp_path)
    assert len(evidence) == 1
    assert evidence[0]["execution_id"] == first.execution_id


async def test_business_critical_execution_is_admin_visible_and_tenant_scoped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="site-critical")
    request = _request(
        tenant_id="tenant-money-a",
        business_id="site-critical",
        goal_type="revenue_funnel_update",
        metadata={"approved_by": "operator-1"},
        constraints=(PolicyConstraint(name="require_human_approval", value=True),),
        idempotency_key="tenant-visible-1",
    )

    result = await service.execute(request)

    assert result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED}
    registry_path = tmp_path / "runtime" / "distributed" / "documents" / "business_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert set(registry["items"].keys()) == {"tenant-money-a:site-critical"}
    artifact_path = tmp_path / "runtime" / "business_autonomy" / f"{result.execution_id}.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["tenant_id"] == "tenant-money-a"
    assert artifact["business_id"] == "site-critical"
