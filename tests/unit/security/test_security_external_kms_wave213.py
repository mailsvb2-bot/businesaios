from security.governance_owner_factory import build_security_governance_infrastructure
from security.kms_provider_backend import KMSProviderSelectionRequest


def test_external_kms_providers_are_registered_and_selectable(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    capabilities = {item.provider_name for item in owner.kms_registry.list_capabilities()}
    assert {'aws-kms', 'gcp-kms', 'vault-transit', 'hardware-hsm'} <= capabilities
    provider, selection = owner.kms_registry.select(KMSProviderSelectionRequest(operation_kind='encrypt', require_hsm_backed_keys=True, preferred_provider_name='hardware-hsm'))
    assert selection.provider_name == 'hardware-hsm'
    handle = provider.create_key(key_id='tenant:acme:key-1', algorithm='rsa-4096', exportable=False)
    assert handle.provider_name == 'hardware-hsm'
