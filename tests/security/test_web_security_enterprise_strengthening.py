from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from app.web.auth import AuthService
from app.web.session import SessionStore
from security.token_policy import TokenPolicy


def test_auth_service_deduplicates_scopes_and_reports_ttl() -> None:
    now = datetime.now(UTC)
    result = AuthService(token_policy=TokenPolicy(max_ttl_seconds=7200)).authenticate(
        {
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=15)).isoformat(),
            'subject': 'user-1',
            'audience': 'api',
            'scopes': 'read write read',
        }
    )
    token = result['payload']['security']['token']
    assert token['scopes'] == ['read', 'write']
    assert token['ttl_seconds'] is not None


def test_session_store_reports_age_and_idle_diagnostics() -> None:
    now = datetime.now(UTC)
    result = SessionStore().build(
        {
            'session_id': 's1',
            'created_at': (now - timedelta(minutes=10)).isoformat(),
            'last_seen_at': (now - timedelta(minutes=2)).isoformat(),
            'now': now.isoformat(),
        }
    )
    security = result['payload']['security']['session']
    assert security['allowed'] is True
    assert security['age_seconds'] >= 600
    assert security['idle_seconds'] >= 120
