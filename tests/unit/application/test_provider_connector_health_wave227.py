from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, *, tenant_id, connector_id, business_id, secret_name, value):
    ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=value.encode('utf-8'))


def test_postgres_health_probe_validates_dsn_shape():
    vault = InMemorySecretVault()
    provider = provider_map()['postgres_runtime']
    _put(vault, tenant_id='tenant-a', connector_id=provider.connector_id, business_id='runtime-a', secret_name=f'{provider.connector_id}.dsn', value='postgres://user:pass@localhost:5432/db')
    result = ProviderConnectorHealthService(vault).probe(provider=provider, tenant_id='tenant-a', business_id='runtime-a', probe_mode='live')
    assert result.status == 'ready_for_live_probe'
    assert result.reason == 'validated_secret_shape'
