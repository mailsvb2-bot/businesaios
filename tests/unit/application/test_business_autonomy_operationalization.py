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


def test_operationalization_cache_is_scoped_to_storage_configuration(tmp_path, monkeypatch) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    monkeypatch.setenv("DATA_DIR", str(first_root))
    first = build_business_autonomy_operationalization()
    assert build_business_autonomy_operationalization() is first

    monkeypatch.setenv("DATA_DIR", str(second_root))
    second = build_business_autonomy_operationalization()

    assert second is not first
    assert build_business_autonomy_operationalization() is second
    view = second["operator_admin_plane"].get_fleet_view(limit=10)
    assert view.fleet_cards


def test_operationalization_storage_key_does_not_retain_raw_postgres_dsn(monkeypatch) -> None:
    from types import SimpleNamespace

    from runtime.business_autonomy import public_api

    secret_dsn = "postgresql://user:super-secret-password@db.example.test/business"
    monkeypatch.setattr(
        public_api,
        "resolve_storage_config",
        lambda: SimpleNamespace(
            env="dev",
            backend="postgres",
            postgres_dsn=secret_dsn,
            postgres_event_store_enabled=True,
        ),
    )

    key = public_api._operationalization_storage_key()

    assert secret_dsn not in key
    assert "super-secret-password" not in "|".join(key)
    assert len(key[3]) == 64
