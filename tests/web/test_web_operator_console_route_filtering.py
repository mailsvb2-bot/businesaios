from __future__ import annotations

from app.web.app import WebApp


def test_web_app_filters_auth_routes_when_not_ready() -> None:
    app = WebApp()
    payload = app.build(
        {
            'tenant_id': 'tenant-a',
            'auth_payload': {
                'issued_at': '2026-03-28T00:00:00+00:00',
                'expires_at': '2026-03-27T00:00:00+00:00',
                'subject': 'user',
                'audience': 'web',
                'issuer': 'issuer',
            },
            'session_payload': {
                'created_at': '2026-03-28T00:00:00+00:00',
                'last_seen_at': '2026-03-28T00:05:00+00:00',
            },
        }
    )
    routes = payload['payload']['routes']['payload']['routes']
    assert routes == ()
    assert payload['payload']['ready'] is False
