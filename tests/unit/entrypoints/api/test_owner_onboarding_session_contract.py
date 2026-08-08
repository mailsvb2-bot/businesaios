from __future__ import annotations

from datetime import timedelta

from entrypoints.api.api_key_policy import ApiKeyPolicy, InMemoryApiKeyStore, utc_now
from entrypoints.api.auth_contract import RequestAuthentication
from governance.rbac_contract import RoleId


def test_owner_onboarding_session_is_short_lived_tenant_bound_and_least_privilege() -> None:
    policy = ApiKeyPolicy(store=InMemoryApiKeyStore(pepper='test-pepper'))
    before = utc_now()
    record, raw_key = policy.issue_owner_session(
        tenant_id='tenant-a',
        business_id='business-a',
        subject='user-a',
        display_name='Acme',
    )

    assert record.roles == (RoleId.OWNER,)
    assert record.scopes == ('provider_control_plane',)
    assert record.metadata['principal_kind'] == 'user'
    assert record.metadata['session_kind'] == 'owner_onboarding'
    assert record.metadata['business_id'] == 'business-a'
    assert record.expires_at is not None
    assert before + timedelta(minutes=59) <= record.expires_at <= before + timedelta(minutes=61)

    allowed = policy.authenticate(RequestAuthentication(tenant_id='tenant-a', api_key=raw_key))
    assert allowed.allowed is True
    assert allowed.principal is not None
    assert allowed.principal.tenant_id == 'tenant-a'
    assert allowed.principal.roles == (RoleId.OWNER,)
    assert allowed.principal.scopes == ('provider_control_plane',)
    assert allowed.principal.metadata['business_id'] == 'business-a'
    assert allowed.principal.metadata['principal_kind'] == 'user'

    denied = policy.authenticate(RequestAuthentication(tenant_id='tenant-b', api_key=raw_key))
    assert denied.allowed is False
    assert denied.reason == 'tenant_mismatch'
