from canon.admin_surface_policy import ADMIN_SURFACE_POLICY


def test_admin_surface_policy_recommends_extended_luxury_artifacts() -> None:
    assert tuple(ADMIN_SURFACE_POLICY['recommended_admin_artifacts']) == (
        'code_navigation',
        'remediation_action',
        'graph_or_metric',
        'patch_suggestion',
        'stop_condition',
        'file_passport',
        'snapshot_diff',
        'live_widget',
        'visual_conflict_map',
        'dashboard_layout',
    )
