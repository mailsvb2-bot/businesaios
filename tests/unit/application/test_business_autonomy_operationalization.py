import pytest

from application.business_autonomy.operationalization import (
    BusinessActiveActiveQuorumService,
    BusinessChaosExecutionService,
    BusinessFinalReadinessReportBuilder,
    BusinessInvariantEnforcementService,
    BusinessOpsDashboardService,
    BusinessRecoveryChaosMatrix,
    BusinessWorkflowRuntimeStub,
)
from runtime.business_autonomy.public_api import build_business_autonomy_operationalization


@pytest.mark.asyncio
async def test_business_workflow_runtime_stub_completes() -> None:
    runtime = BusinessWorkflowRuntimeStub()
    assert await runtime.start_workflow(workflow_id="w1", workflow_type="cutover", payload={"x": 1}) is True
    assert await runtime.complete_workflow(workflow_id="w1", result={"ok": True}) is True


def test_business_chaos_execution_service_accepts_known_dry_run() -> None:
    service = BusinessChaosExecutionService(BusinessRecoveryChaosMatrix())
    result = service.execute(scenario_name="barrier_restart_recovery", dry_run=True)
    assert result["accepted"] is True
    assert result["executed"] is False


@pytest.mark.asyncio
async def test_business_active_active_quorum_service_reaches_quorum() -> None:
    service = BusinessActiveActiveQuorumService(min_acks=2)
    decision = await service.evaluate(primary_region="eu", secondary_region="us")
    assert decision.quorum_reached is True


def test_business_invariant_enforcement_service_returns_ok() -> None:
    result = BusinessInvariantEnforcementService().enforce()
    assert result["ok"] is True


def test_business_ops_dashboard_service_returns_cards() -> None:
    dashboard = BusinessOpsDashboardService().get_dashboard()
    assert "health_cards" in dashboard and len(dashboard["health_cards"]) >= 1


def test_business_final_readiness_report_builder_builds_report() -> None:
    report = BusinessFinalReadinessReportBuilder().build(
        invariant_ok=True,
        dashboard_ok=True,
        quorum_ok=True,
        chaos_matrix_present=True,
    )
    assert report.overall_ready is True
    assert len(report.checks) == 4


def test_runtime_business_autonomy_public_api_builds_operationalization() -> None:
    stack = build_business_autonomy_operationalization()
    assert "workflow_runtime" in stack
    assert "dashboard_service" in stack
    assert "readiness_report_builder" in stack
