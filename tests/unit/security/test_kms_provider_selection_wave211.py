from __future__ import annotations

from security.kms_provider_backend import KMSProviderSelectionRequest
from security.kms_provider_inmemory import InMemoryKMSProvider
from security.kms_provider_local_hsm_adapter import LocalHSMKMSAdapter
from security.kms_provider_registry import KMSProviderRegistry


def test_kms_registry_prefers_hsm_backed_provider_when_required(tmp_path) -> None:
    registry = KMSProviderRegistry()
    registry.register(InMemoryKMSProvider(provider_name='mem'))
    registry.register(LocalHSMKMSAdapter(str(tmp_path / 'local_hsm.sqlite3'), provider_name='hsm'))

    provider, selection = registry.select(
        KMSProviderSelectionRequest(operation_kind='wrap_secret', require_hsm_backed_keys=True)
    )

    assert selection.provider_name == 'hsm'
    assert selection.capability.supports_hsm_backed_keys is True
    handle = provider.create_key(key_id='tenant-a/master', algorithm='hmac-sha256')
    assert handle.provider_name == 'hsm'
    assert handle.exportable is False
