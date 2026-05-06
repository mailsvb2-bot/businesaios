from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.web.auth import AuthService
from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider


def test_auth_service_rejects_unknown_key_id_fail_closed() -> None:
    now = datetime.now(timezone.utc)
    result = AuthService(key_provider=InMemoryKeyProvider()).authenticate(
        {
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=15)).isoformat(),
            'subject': 'user-1',
            'audience': 'api',
            'key_id': 'missing-key',
        }
    )
    assert result['payload']['security']['token']['allowed'] is False
    assert result['payload']['security']['token']['reason'] == 'unknown_key_id'
    assert result['payload']['auth_context']['signing_material_registered'] is False


def test_auth_service_rejects_wrong_key_purpose() -> None:
    now = datetime.now(timezone.utc)
    provider = InMemoryKeyProvider()
    provider.issue_key(key_id='enc-key', purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='tenant-a')
    result = AuthService(key_provider=provider).authenticate(
        {
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=15)).isoformat(),
            'subject': 'user-1',
            'audience': 'api',
            'tenant_id': 'tenant-a',
            'key_id': 'enc-key',
        }
    )
    assert result['payload']['security']['token']['allowed'] is False
    assert result['payload']['security']['token']['reason'] == 'key_purpose_not_allowed'
    assert result['payload']['auth_context']['signing_material_purpose_allowed'] is False


def test_auth_service_rejects_tenant_mismatch() -> None:
    now = datetime.now(timezone.utc)
    provider = InMemoryKeyProvider()
    provider.issue_key(key_id='request-key', purpose=KeyPurpose.REQUEST_SIGNING, tenant_id='tenant-b', connector_id='crm-a')
    result = AuthService(key_provider=provider).authenticate(
        {
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=15)).isoformat(),
            'subject': 'user-1',
            'audience': 'api',
            'tenant_id': 'tenant-a',
            'connector_id': 'crm-a',
            'key_id': 'request-key',
        }
    )
    assert result['payload']['security']['token']['allowed'] is False
    assert result['payload']['security']['token']['reason'] == 'key_tenant_mismatch'
    assert result['payload']['auth_context']['signing_material_reason'] == 'key_tenant_mismatch'


def test_auth_service_rejects_connector_mismatch() -> None:
    now = datetime.now(timezone.utc)
    provider = InMemoryKeyProvider()
    provider.issue_key(key_id='request-key', purpose=KeyPurpose.REQUEST_SIGNING, tenant_id='tenant-a', connector_id='crm-b')
    result = AuthService(key_provider=provider).authenticate(
        {
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=15)).isoformat(),
            'subject': 'user-1',
            'audience': 'api',
            'tenant_id': 'tenant-a',
            'connector_id': 'crm-a',
            'key_id': 'request-key',
        }
    )
    assert result['payload']['security']['token']['allowed'] is False
    assert result['payload']['security']['token']['reason'] == 'key_connector_mismatch'
    assert result['payload']['auth_context']['signing_material_reason'] == 'key_connector_mismatch'
