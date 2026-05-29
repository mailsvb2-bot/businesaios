from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from app.web.app import WebApp
from app.web.routes import RouteDefinition, Routes


def test_routes_default_catalog_contains_operator_console_pages() -> None:
    result = Routes().build_default(tenant_id='tenant-1')
    assert result['kind'] == 'route_table'
    paths = {row['path'] for row in result['payload']['routes']}
    assert '/web/admin' in paths
    assert '/web/security' in paths
    assert result['payload']['summary']['auth_required_count'] >= 1


def test_routes_mark_tenant_required_when_missing_tenant() -> None:
    result = Routes().build(
        {
            'routes': (
                RouteDefinition(path='/web/admin', page='AdminPage', tenant_required=True),
            ),
        }
    )
    assert result['payload']['routes'][0]['status'] == 'tenant_required'


def test_web_app_assembles_auth_session_and_routes() -> None:
    now = datetime.now(UTC)
    result = WebApp().build(
        {
            'tenant_id': 'tenant-1',
            'auth_payload': {
                'tenant_id': 'tenant-1',
                'issued_at': (now - timedelta(minutes=5)).isoformat(),
                'expires_at': (now + timedelta(minutes=30)).isoformat(),
                'subject': 'user-1',
                'audience': 'web',
            },
            'session_payload': {
                'tenant_id': 'tenant-1',
                'created_at': (now - timedelta(minutes=10)).isoformat(),
                'last_seen_at': (now - timedelta(minutes=1)).isoformat(),
            },
            'routes_payload': {'tenant_id': 'tenant-1'},
        }
    )
    assert result['kind'] == 'web_app'
    assert result['payload']['tenant_bound'] is True
    assert result['payload']['security_summary']['auth_allowed'] is True
    assert result['payload']['security_summary']['session_allowed'] is True
    assert result['payload']['ready'] is True


def test_web_app_fail_closed_when_security_inputs_missing() -> None:
    result = WebApp().build({'title': 'Admin Console'})
    assert result['payload']['security_summary']['auth_allowed'] is False
    assert result['payload']['security_summary']['session_allowed'] is False
    assert result['payload']['ready'] is False
