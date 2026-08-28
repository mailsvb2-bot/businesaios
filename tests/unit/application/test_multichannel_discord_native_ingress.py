from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault: InMemorySecretVault, *, name: str, value: str) -> None:
    provider = provider_map()['discord_messaging']
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.{name}')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=value.encode())


def _native_fixture() -> tuple[ProviderWebhookRuntime, bytes, dict[str, str]]:
    vault = InMemorySecretVault()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()
    _put(vault, name='webhook_secret', value='bridge-secret')
    _put(vault, name='application_public_key', value=public_key)
    body = b'{"type":1,"id":"interaction-1"}'
    timestamp = '1787945000'
    signature = private_key.sign(timestamp.encode() + body).hex()
    return ProviderWebhookRuntime(vault), body, {'X-Signature-Timestamp': timestamp, 'X-Signature-Ed25519': signature}


def test_discord_native_ed25519_signature_is_verified_fail_closed() -> None:
    provider = provider_map()['discord_messaging']
    runtime, body, headers = _native_fixture()
    contract = runtime.describe(provider)
    assert contract.verification_kind == 'discord_ed25519_or_shared_secret'
    assert contract.metadata['native_public_key_field'] == 'application_public_key'
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body + b' ') is False
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Signature-Ed25519': headers['X-Signature-Ed25519']}, body=body) is False


def test_discord_native_signature_rejects_malformed_key_and_signature() -> None:
    provider = provider_map()['discord_messaging']
    runtime, body, headers = _native_fixture()
    broken = dict(headers, **{'X-Signature-Ed25519': 'zz' * 64})
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=broken, body=body) is False
    vault = InMemorySecretVault()
    _put(vault, name='webhook_secret', value='bridge-secret')
    _put(vault, name='application_public_key', value='00')
    assert ProviderWebhookRuntime(vault).verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body) is False


def test_discord_bridge_shared_secret_fallback_remains_supported() -> None:
    provider = provider_map()['discord_messaging']
    vault = InMemorySecretVault()
    _put(vault, name='webhook_secret', value='bridge-secret')
    runtime = ProviderWebhookRuntime(vault)
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=b'{}') is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'wrong'}, body=b'{}') is False


def test_discord_catalog_exposes_separate_optional_application_public_key() -> None:
    fields = {field.secret_name: field for field in provider_map()['discord_messaging'].secret_fields}
    assert fields['webhook_secret'].required is True
    assert fields['application_public_key'].required is False
    assert fields['application_public_key'].secret_kind == 'config'
