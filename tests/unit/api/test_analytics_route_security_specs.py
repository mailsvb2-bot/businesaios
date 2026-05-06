from __future__ import annotations

from entrypoints.api.control_plane_security_guard import ControlPlaneSecurityGuard
from entrypoints.api.public_surface_security_guard import _ROUTE_SPECS
from security.access_policy import SecurityAction


def test_public_analytics_routes_have_security_specs() -> None:
    business = _ROUTE_SPECS['/analytics/business/{tenant_id}']
    dashboard = _ROUTE_SPECS['/analytics/dashboard/{tenant_id}']
    assert business.resource_type == 'analytics_scorecard'
    assert dashboard.resource_type == 'analytics_dashboard'
    assert business.action is SecurityAction.READ
    assert dashboard.action is SecurityAction.READ


def test_control_plane_analytics_routes_have_security_specs() -> None:
    materialize = ControlPlaneSecurityGuard._spec_for('api.control_plane.analytics.materialize')
    enqueue = ControlPlaneSecurityGuard._spec_for('api.control_plane.analytics.enqueue_materialization')
    signed_export = ControlPlaneSecurityGuard._spec_for('api.control_plane.analytics.signed_export')
    assert materialize.resource_type == 'analytics_materialization'
    assert enqueue.resource_type == 'analytics_materialization'
    assert signed_export.resource_type == 'analytics_export'
    assert materialize.action is SecurityAction.ADMIN
    assert signed_export.requires_export_posture is True
