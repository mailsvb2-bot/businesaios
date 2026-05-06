from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


class _OkTransport:
    def execute(self, **kwargs):
        return {'http_status': 200, 'response_body': '{"ok":true}'}


class _FailTransport:
    def execute(self, **kwargs):
        return {'http_status': 503, 'response_body': 'down'}


def _put(vault, *, tenant_id, connector_id, business_id, secret_name, value):
    ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=value.encode('utf-8'))


def test_live_probe_emits_messaging_health_signal_and_updates_registry_on_success():
    vault = InMemorySecretVault()
    provider = provider_map()['telegram_bot']
    _put(vault, tenant_id='tenant-a', connector_id=provider.connector_id, business_id='biz-a', secret_name=f'{provider.connector_id}.bot_token', value='123:abc')
    registry = ChannelHealthRegistry()
    runtime = ProviderLiveProbeRuntime(vault, transports={'telegram_bot': _OkTransport()}, channel_health_registry=registry)
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    signal = dict(result.metadata).get('messaging_health_signal', {})
    assert result.status == 'probe_live_ok'
    assert signal.get('channel') == 'telegram'
    assert signal.get('healthy') is True
    assert registry.get('telegram').healthy is True


def test_live_probe_updates_registry_on_failure_for_messaging_provider():
    vault = InMemorySecretVault()
    provider = provider_map()['telegram_bot']
    _put(vault, tenant_id='tenant-a', connector_id=provider.connector_id, business_id='biz-a', secret_name=f'{provider.connector_id}.bot_token', value='123:abc')
    registry = ChannelHealthRegistry()
    runtime = ProviderLiveProbeRuntime(vault, transports={'telegram_bot': _FailTransport()}, channel_health_registry=registry)
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    signal = dict(result.metadata).get('messaging_health_signal', {})
    assert result.status == 'probe_live_failed'
    assert signal.get('healthy') is False
    assert registry.get('telegram').healthy is False
