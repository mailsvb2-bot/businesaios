from __future__ import annotations

import json
from pathlib import Path

import pytest

from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
    PolicyConstraint,
)
from application.business_autonomy.execution_subject import business_execution_approval_id
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from entrypoints.api.approval_route_handlers import ApprovalRouteHandlers
from governance.approval_contract import ApprovalOutcome
from governance.rbac_contract import RoleId
from runtime.business_autonomy.bootstrap import (
    build_business_autonomy_admin_dependencies,
    build_business_autonomy_guarded_service,
)

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
    simulation: bool = False,
) -> BusinessExecutionRequest:
    final_metadata = {"tenant_id": tenant_id, "planning_horizon": "week", **dict(metadata or {})}
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id=business_id,
            goal_id=goal_id,
            goal_type=goal_type,
            goal_payload={"estimated_cost": estimated_cost, "outbound_count": outbound_count},
            simulation=simulation,
            constraints=constraints,
            metadata=final_metadata,
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id=f"corr:{tenant_id}:{business_id}:{goal_id}:{idempotency_key}",
        idempotency_key=idempotency_key,
    )


def _onboarded_service(*, tenant_id: str, business_id: str):
    dependencies = build_business_autonomy_admin_dependencies()
    dependencies["onboarding"].onboard(
        BusinessOnboardingRequest(
            business_id=business_id,
            tenant_id=tenant_id,
            ownership_key=f"verified-owner:{tenant_id}:{business_id}",
            region="eu-west-1",
            channel_kind=ChannelKind.WEBSITE,
            adapter_key="website.default",
            external_ref=f"https://{business_id}.example.test",
            requested_by="business-critical-test-onboarding",
            metadata={"verified_owner": True, "non_ai_mode": "supervised"},
        )
    )
    return build_business_autonomy_guarded_service(business_id=business_id)


def _approve_canonical_request(service, request: BusinessExecutionRequest) -> None:
    ApprovalRouteHandlers(approval_store=service._approval_gate._store).evaluate(
        approval_id=business_execution_approval_id(request),
        tenant_id=str(request.envelope.metadata["tenant_id"]),
        actor_id="operator-1",
        role_id=RoleId.OWNER,
        outcome=ApprovalOutcome.APPROVE,
        rationale="Approved through canonical governance store.",
    )


async def _execute_after_canonical_approval(service, request: BusinessExecutionRequest):
    pending = await service.execute(request)
    assert pending.verdict is ExecutionVerdict.PARTIAL
    _approve_canonical_request(service, request)
    return await service.execute(request)


def _evidence_lines(data_dir: Path) -> list[dict]:
    path = data_dir / "business_autonomy" / "evidence.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def test_money_or_live_write_requires_approval_before_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = _onboarded_service(tenant_id="tenant-critical", business_id="site-critical")

    result = await service.execute(
        _request(
            goal_type="paid_campaign_launch",
            constraints=(
                PolicyConstraint(name="monthly_budget_limit", value=50.0),
                PolicyConstraint(name="outbound_message_limit", value=25),
                PolicyConstraint(name="require_human_approval", value=True),
            ),
        )
    )

    assert result.verdict is ExecutionVerdict.PARTIAL
    assert result.metadata["approval_status"] == "pending"
    assert _evidence_lines(tmp_path) == []


async def test_budget_guard_blocks_spend_above_limit_without_side_effects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = _onboarded_service(tenant_id="tenant-critical", business_id="site-critical")

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
    service = _onboarded_service(tenant_id="tenant-critical", business_id="site-critical")

    result = await service.execute(
        _request(
            goal_type="funnel_broadcast",
            estimated_cost=0.0,
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
    service = _onboarded_service(tenant_id="tenant-critical", business_id="site-critical")
    request = _request(
        goal_type="paid_campaign_launch",
        constraints=(
            PolicyConstraint(name="monthly_budget_limit", value=50.0),
            PolicyConstraint(name="outbound_message_limit", value=25),
            PolicyConstraint(name="require_human_approval", value=True),
        ),
        idempotency_key="duplicate-webhook-1",
        simulation=True,
    )

    first = await _execute_after_canonical_approval(service, request)
    second = await service.execute(request)

    assert first.verdict is ExecutionVerdict.SIMULATED
    assert second == first
    evidence = _evidence_lines(tmp_path)
    assert len(evidence) == 1
    assert evidence[0]["execution_id"] == first.execution_id


async def test_approval_and_idempotency_reject_changed_execution_subject(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = _onboarded_service(tenant_id="tenant-critical", business_id="site-critical")
    constraints = (
        PolicyConstraint(name="monthly_budget_limit", value=50.0),
        PolicyConstraint(name="outbound_message_limit", value=25),
        PolicyConstraint(name="require_human_approval", value=True),
    )
    approved_request = _request(
        goal_type="paid_campaign_launch",
        estimated_cost=10.0,
        constraints=constraints,
        idempotency_key="subject-bound-1",
        simulation=True,
    )

    pending = await service.execute(approved_request)
    assert pending.verdict is ExecutionVerdict.PARTIAL
    _approve_canonical_request(service, approved_request)

    changed_request = _request(
        goal_type="paid_campaign_launch",
        estimated_cost=20.0,
        constraints=constraints,
        idempotency_key="subject-bound-1",
        simulation=True,
    )
    changed = await service.execute(changed_request)
    original = await service.execute(approved_request)

    assert changed.verdict is ExecutionVerdict.PARTIAL
    assert changed.metadata["approval_status"] == "pending"
    assert business_execution_approval_id(changed_request) != business_execution_approval_id(approved_request)
    assert original.verdict is ExecutionVerdict.SIMULATED
    assert len(_evidence_lines(tmp_path)) == 1


async def test_business_critical_execution_is_admin_visible_and_tenant_scoped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = _onboarded_service(tenant_id="tenant-money-a", business_id="site-critical")
    request = _request(
        tenant_id="tenant-money-a",
        business_id="site-critical",
        goal_type="revenue_funnel_update",
        constraints=(
            PolicyConstraint(name="monthly_budget_limit", value=50.0),
            PolicyConstraint(name="outbound_message_limit", value=25),
            PolicyConstraint(name="require_human_approval", value=True),
        ),
        idempotency_key="tenant-visible-1",
        simulation=True,
    )

    result = await _execute_after_canonical_approval(service, request)

    assert result.verdict is ExecutionVerdict.SIMULATED
    registry_record = service._distributed_business_registry.get("tenant-money-a", "site-critical")
    assert registry_record is not None
    assert registry_record.tenant_id == "tenant-money-a"
    assert registry_record.business_id == "site-critical"
    artifact_path = tmp_path / "runtime" / "business_autonomy" / f"{result.execution_id}.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["tenant_id"] == "tenant-money-a"
    assert artifact["business_id"] == "site-critical"
