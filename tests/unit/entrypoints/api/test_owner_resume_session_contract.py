from __future__ import annotations

from datetime import timedelta

from entrypoints.api.api_key_policy import (
    OWNER_SESSION_RESUME_SCOPE,
    ApiKeyPolicy,
    InMemoryApiKeyStore,
    utc_now,
)
from entrypoints.api.auth_contract import RequestAuthentication
from governance.rbac_contract import RoleId


def test_owner_resume_session_is_narrow_tenant_bound_and_can_only_mint_fresh_owner_session() -> None:
    policy = ApiKeyPolicy(store=InMemoryApiKeyStore(pepper='test-pepper'))
    before = utc_now()
    resume_record, raw_resume = policy.issue_owner_resume_session(
        tenant_id='tenant-a',
        business_id='business-a',
        intake_id='cta-a',
        subject='user-a',
        display_name='Acme',
    )

    assert resume_record.roles == ()
    assert resume_record.scopes == (OWNER_SESSION_RESUME_SCOPE,)
    assert 'provider_control_plane' not in resume_record.scopes
    assert resume_record.metadata['session_kind'] == 'owner_onboarding_resume'
    assert resume_record.metadata['business_id'] == 'business-a'
    assert resume_record.metadata['intake_id'] == 'cta-a'
    assert resume_record.expires_at is not None
    assert before + timedelta(hours=23, minutes=59) <= resume_record.expires_at <= before + timedelta(days=1, minutes=1)

    resume_verdict = policy.authenticate(RequestAuthentication(tenant_id='tenant-a', api_key=raw_resume))
    assert resume_verdict.allowed is True
    assert resume_verdict.principal is not None
    assert resume_verdict.principal.roles == ()
    assert resume_verdict.principal.scopes == (OWNER_SESSION_RESUME_SCOPE,)

    resumed = policy.resume_owner_session(
        resume_key=raw_resume,
        intake_id='cta-a',
        tenant_id='tenant-a',
        business_id='business-a',
    )
    assert resumed is not None
    owner_record, raw_owner = resumed
    assert raw_owner != raw_resume
    assert owner_record.roles == (RoleId.OWNER,)
    assert owner_record.scopes == ('provider_control_plane',)
    assert owner_record.metadata['session_kind'] == 'owner_onboarding'
    assert owner_record.metadata['business_id'] == 'business-a'

    owner_verdict = policy.authenticate(RequestAuthentication(tenant_id='tenant-a', api_key=raw_owner))
    assert owner_verdict.allowed is True
    assert owner_verdict.principal is not None
    assert owner_verdict.principal.scopes == ('provider_control_plane',)


def test_owner_resume_session_fails_closed_on_intake_business_or_tenant_mismatch() -> None:
    policy = ApiKeyPolicy(store=InMemoryApiKeyStore(pepper='test-pepper'))
    _, raw_resume = policy.issue_owner_resume_session(
        tenant_id='tenant-a',
        business_id='business-a',
        intake_id='cta-a',
        subject='user-a',
    )

    assert policy.resume_owner_session(
        resume_key=raw_resume,
        intake_id='cta-other',
        tenant_id='tenant-a',
        business_id='business-a',
    ) is None
    assert policy.resume_owner_session(
        resume_key=raw_resume,
        intake_id='cta-a',
        tenant_id='tenant-a',
        business_id='business-other',
    ) is None
    assert policy.resume_owner_session(
        resume_key=raw_resume,
        intake_id='cta-a',
        tenant_id='tenant-other',
        business_id='business-a',
    ) is None


def test_owner_account_session_is_navigation_only_and_can_resume_only_same_owner_membership() -> None:
    policy = ApiKeyPolicy(store=InMemoryApiKeyStore(pepper='test-pepper'))
    account_record, raw_account = policy.issue_owner_account_session(
        tenant_id='tenant-a',
        owner_account_id='owner-account-a',
        subject='user-a',
        display_name='Acme',
    )

    assert account_record.roles == ()
    assert account_record.scopes == ('owner_account_resume',)
    assert 'provider_control_plane' not in account_record.scopes
    assert policy.resolve_owner_account_session(resume_key=raw_account) == ('owner-account-a', 'user-a')

    assert policy.resume_owner_account_business(
        resume_key=raw_account,
        owner_account_id='owner-account-other',
        subject='user-a',
        tenant_id='tenant-b',
        business_id='business-b',
    ) is None
    assert policy.resume_owner_account_business(
        resume_key=raw_account,
        owner_account_id='owner-account-a',
        subject='user-other',
        tenant_id='tenant-b',
        business_id='business-b',
    ) is None

    resumed = policy.resume_owner_account_business(
        resume_key=raw_account,
        owner_account_id='owner-account-a',
        subject='user-a',
        tenant_id='tenant-b',
        business_id='business-b',
    )
    assert resumed is not None
    owner_record, raw_owner = resumed
    assert owner_record.tenant_id == 'tenant-b'
    assert owner_record.subject == 'user-a'
    assert owner_record.roles == (RoleId.OWNER,)
    assert owner_record.scopes == ('provider_control_plane',)
    assert owner_record.metadata['business_id'] == 'business-b'
    assert policy.authenticate(RequestAuthentication(tenant_id='tenant-b', api_key=raw_owner)).allowed is True


def test_owner_account_session_refresh_threshold_is_narrow_and_expiry_aware() -> None:
    policy = ApiKeyPolicy(store=InMemoryApiKeyStore(pepper='test-pepper'))
    _, long_lived = policy.issue_owner_account_session(
        tenant_id='tenant-a', owner_account_id='account-a', subject='user-a', ttl_seconds=86400,
    )
    _, near_expiry = policy.issue_owner_account_session(
        tenant_id='tenant-a', owner_account_id='account-a', subject='user-a', ttl_seconds=60,
    )
    _, business_resume = policy.issue_owner_resume_session(
        tenant_id='tenant-a', business_id='business-a', intake_id='cta-a', subject='user-a', ttl_seconds=60,
    )

    assert policy.owner_account_session_needs_refresh(resume_key=long_lived, within_seconds=3600) is False
    assert policy.owner_account_session_needs_refresh(resume_key=near_expiry, within_seconds=3600) is True
    assert policy.owner_account_session_needs_refresh(resume_key=business_resume, within_seconds=3600) is False
    assert policy.owner_account_session_needs_refresh(resume_key='not-a-key', within_seconds=3600) is False
