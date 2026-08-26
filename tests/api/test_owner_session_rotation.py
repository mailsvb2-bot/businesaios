from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore, RequestAuthentication
from governance.rbac_contract import RoleId


def _allowed(policy: ApiKeyPolicy, token: str) -> bool:
    return policy.authenticate(RequestAuthentication(api_key=token, tenant_id='tenant-a')).allowed


def test_resume_revokes_only_prior_owner_onboarding_sessions(tmp_path) -> None:
    store = PersistentApiKeyStore(path=tmp_path / 'keys.json', pepper='pep')
    policy = ApiKeyPolicy(store=store)
    _, old = policy.issue_owner_session(tenant_id='tenant-a', business_id='business-a', subject='owner-a')
    _, resume = policy.issue_owner_resume_session(tenant_id='tenant-a', business_id='business-a', intake_id='intake-a', subject='owner-a')
    _, regular_owner = store.issue(tenant_id='tenant-a', subject='owner-a', roles=(RoleId.OWNER,))
    _, other_business = policy.issue_owner_session(tenant_id='tenant-a', business_id='business-b', subject='owner-a')

    first = policy.resume_owner_session(resume_key=resume, intake_id='intake-a', tenant_id='tenant-a', business_id='business-a')
    assert first is not None
    _, first_key = first
    assert _allowed(policy, first_key)
    assert not _allowed(policy, old)
    assert _allowed(policy, regular_owner)
    assert _allowed(policy, other_business)

    second = policy.resume_owner_session(resume_key=resume, intake_id='intake-a', tenant_id='tenant-a', business_id='business-a')
    assert second is not None
    _, second_key = second
    assert second_key != first_key
    assert _allowed(policy, second_key)
    assert not _allowed(policy, first_key)
    assert _allowed(policy, regular_owner)
    assert _allowed(policy, other_business)


def test_persisted_rotation_is_visible_to_existing_reader(tmp_path) -> None:
    path = tmp_path / 'keys.json'
    writer = ApiKeyPolicy(store=PersistentApiKeyStore(path=path, pepper='pep'))
    _, old = writer.issue_owner_session(tenant_id='tenant-a', business_id='business-a', subject='owner-a')
    _, resume = writer.issue_owner_resume_session(tenant_id='tenant-a', business_id='business-a', intake_id='intake-a', subject='owner-a')
    reader = ApiKeyPolicy(store=PersistentApiKeyStore(path=path, pepper='pep'))
    assert _allowed(reader, old)

    rotated = writer.resume_owner_session(resume_key=resume, intake_id='intake-a', tenant_id='tenant-a', business_id='business-a')
    assert rotated is not None
    assert not _allowed(reader, old)
    assert _allowed(reader, rotated[1])


def test_concurrent_resume_leaves_exactly_one_active_owner_session(tmp_path) -> None:
    path = tmp_path / 'keys.json'
    seed = ApiKeyPolicy(store=PersistentApiKeyStore(path=path, pepper='pep'))
    _, old = seed.issue_owner_session(tenant_id='tenant-a', business_id='business-a', subject='owner-a')
    _, resume = seed.issue_owner_resume_session(tenant_id='tenant-a', business_id='business-a', intake_id='intake-a', subject='owner-a')
    policies = [ApiKeyPolicy(store=PersistentApiKeyStore(path=path, pepper='pep')) for _ in range(2)]

    def rotate(policy: ApiKeyPolicy):
        return policy.resume_owner_session(resume_key=resume, intake_id='intake-a', tenant_id='tenant-a', business_id='business-a')

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rotate, policies))
    tokens = [result[1] for result in results if result is not None]
    assert len(tokens) == 2

    final_store = PersistentApiKeyStore(path=path, pepper='pep')
    final_policy = ApiKeyPolicy(store=final_store)
    assert not _allowed(final_policy, old)
    assert sum(_allowed(final_policy, token) for token in tokens) == 1
    active = [record for record in final_store.list_records() if record.is_active() and record.metadata.get('session_kind') == 'owner_onboarding' and record.metadata.get('business_id') == 'business-a']
    assert len(active) == 1
