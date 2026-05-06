from __future__ import annotations

from governance.rbac_contract import RoleId
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore, RequestAuthentication


def test_persistent_api_key_store_roundtrip(tmp_path) -> None:
    path = tmp_path / 'api_keys.json'
    store = PersistentApiKeyStore(path=path, pepper='pep')
    record, token = store.issue(tenant_id='tenant-a', subject='svc', roles=(RoleId.OWNER,))
    reloaded = PersistentApiKeyStore(path=path, pepper='pep')
    verdict = ApiKeyPolicy(store=reloaded).authenticate(RequestAuthentication(api_key=token, tenant_id='tenant-a'))
    assert verdict.allowed is True
    assert verdict.principal is not None
    assert verdict.principal.tenant_id == 'tenant-a'
