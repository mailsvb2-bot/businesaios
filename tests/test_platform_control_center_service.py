from __future__ import annotations

from application.admin.platform_control_center_service import (
    PLATFORM_ADMIN_RUNTIME_MODE,
    PlatformControlCenterService,
)


def test_platform_control_center_reports_advisory_not_live_ready(tmp_path):
    service = PlatformControlCenterService.for_repo(tmp_path)

    overview = service.build_overview(tenant_id="tenant-demo", business_id="biz-demo")
    widget_runtime = service.build_widget_runtime(tenant_id="tenant-demo", business_id="biz-demo")
    stop_conditions = service.build_stop_conditions()

    assert overview["runtime_mode"] == PLATFORM_ADMIN_RUNTIME_MODE == "read_only_advisory"
    assert overview["canon_status"]["production_ready"] is False
    assert widget_runtime["live_ready"] is False
    assert widget_runtime["runtime"] == "read_only_advisory"
    assert stop_conditions["status"] == "not_closed"
    assert {row["state"] for row in stop_conditions["rows"]} == {"open"}


def test_platform_control_center_does_not_emit_fake_remediation_patch(tmp_path):
    service = PlatformControlCenterService.for_repo(tmp_path)

    result = service.build_remediation_run(
        file_path="application/admin/platform_control_center_service.py",
        risk_type="static_optimism",
    )

    assert result["status"] == "manual_review_required"
    assert result["patch_code"] is None
    assert "pretend" in result["reason"]


def test_snapshot_and_maturity_surfaces_do_not_claim_unwired_proof(tmp_path):
    service = PlatformControlCenterService.for_repo(tmp_path)

    diff = service.build_snapshot_diff_view(tenant_id="tenant-demo")
    trends = service.build_maturity_trends(tenant_id="tenant-demo")
    risk_diff = service.build_risk_diff(tenant_id="tenant-demo")

    assert diff["snapshot_available"] is False
    assert diff["changed_files"] is None
    assert trends["trend_available"] is False
    assert trends["maturity_trend_rows"][0]["maturity"] is None
    assert risk_diff["snapshot_available"] is False
    assert "unavailable" in risk_diff["summary"]
