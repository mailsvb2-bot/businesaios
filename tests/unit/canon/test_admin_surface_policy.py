from canon.admin_surface_policy import ADMIN_SURFACE_POLICY, AdminSurfaceDeclaration, assert_admin_surface_declared


def test_admin_surface_policy_requires_three_artifacts() -> None:
    assert ADMIN_SURFACE_POLICY['new_feature_must_be_visible_in_admin'] is True
    assert tuple(ADMIN_SURFACE_POLICY['required_admin_artifacts']) == (
        'page_or_panel', 'control_plane_endpoint', 'risk_or_status_visibility'
    )


def test_admin_surface_declaration_validates() -> None:
    declaration = AdminSurfaceDeclaration(
        feature_name='provider_activation',
        page_or_panel='PlatformControlCenterPage',
        control_plane_endpoint='/control-plane/provider-admin/activate',
        risk_or_status_visibility='platform-overview.provider_rows',
    )
    assert_admin_surface_declared(declaration)
