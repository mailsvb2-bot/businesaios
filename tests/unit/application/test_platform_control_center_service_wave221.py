from pathlib import Path

from application.admin.platform_control_center_service import PlatformControlCenterService


def test_platform_control_center_exposes_luxury_admin_surfaces() -> None:
    service = PlatformControlCenterService.for_repo()
    overview = service.build_overview(tenant_id='tenant-demo', business_id='site-alpha')
    assert 'dependency_rows' in overview
    assert 'remediation_rows' in overview
    assert 'risk_diff' in overview
    assert 'ownership_rows' in overview
    assert 'patch_suggestions' in overview
    assert 'stop_conditions' in overview
    assert overview['admin_contract']['recommended_admin_artifacts']
    assert 'live_widget_bundle' in overview
    assert 'visual_conflict_map' in overview
    if overview['risk_rows']:
        assert overview['risk_rows'][0]['code_navigation']['editor_hint']
        assert 'stop_condition' in overview['risk_rows'][0]


def test_platform_control_center_builds_remediation_workflow_and_trends() -> None:
    service = PlatformControlCenterService.for_repo()
    workflow = service.build_remediation_workflow(file_path='application/admin/platform_control_center_service.py', risk_type='large_module')
    trends = service.build_risk_trends(tenant_id='tenant-demo')
    assert workflow['workflow_steps']
    assert workflow['code_navigation']['editor_hint']
    assert 'trend_rows' in trends


def test_platform_control_center_builds_file_passport_and_maturity_trends() -> None:
    service = PlatformControlCenterService.for_repo()
    passport = service.build_file_passport(file_path='application/admin/platform_control_center_service.py')
    trends = service.build_maturity_trends(tenant_id='tenant-demo')
    remediation = service.build_remediation_run(file_path='application/admin/platform_control_center_service.py', risk_type='large_module')
    assert passport['code_navigation']['editor_hint']
    assert 'dependency_context' in passport
    assert passport['passport_cards']['structure']['python_lines'] >= 1
    assert 'trend_rows' in trends
    assert remediation['status'] == 'prepared'
    assert remediation['patch_code']


def test_platform_control_center_service_is_not_god_module_anymore() -> None:
    lines = Path('application/admin/platform_control_center_service.py').read_text(encoding='utf-8').splitlines()
    assert len(lines) < 320
