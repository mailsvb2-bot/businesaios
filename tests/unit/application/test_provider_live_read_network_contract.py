from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime._internal.http_transport import SyncHTTPResult
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, business_id: str, name: str, value: str) -> None:
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope=business_id, secret_name=f'{provider.connector_id}.{name}')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=value.encode())


def test_telegram_live_read_uses_get_updates_without_internal_control_body(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['telegram_bot'], InMemorySecretVault(), []
    _put(vault, provider, 'biz-a', 'bot_token', '123:abc')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={'ok': True, 'result': []}, text='{"ok": true, "result": []}')))
    result = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={})
    assert result.status == 'live_executed' and result.accepted is True
    assert calls[0]['method'] == 'GET' and calls[0]['url'] == 'https://api.telegram.org/bot123:abc/getUpdates' and calls[0]['body'] is None
    assert result.metadata['parsed_response']['resource_count'] == 0


def test_telegram_live_probe_uses_get_me(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['telegram_bot'], InMemorySecretVault(), []
    _put(vault, provider, 'biz-a', 'bot_token', '123:abc')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={'ok': True, 'result': {'id': 7}}, text='{"ok": true, "result": {"id": 7}}')))
    result = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    assert result.status == 'probe_live_ok' and result.ok is True
    assert calls[0]['url'] == 'https://api.telegram.org/bot123:abc/getMe' and calls[0]['method'] == 'GET'


def test_hubspot_live_read_uses_current_contacts_api_and_nested_cursor(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['hubspot'], InMemorySecretVault(), []
    _put(vault, provider, 'hub-a', 'private_app_token', 'pat-test')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"results":[{"id":"1"}],"paging":{"next":{"after":"2"}}}')))
    result = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='hub-a', operation='contact_sync', mode='live', payload={})
    assert result.status == 'live_executed' and result.accepted is True
    assert calls[0]['url'] == 'https://api.hubapi.com/crm/objects/2026-03/contacts' and calls[0]['method'] == 'GET' and calls[0]['body'] is None
    assert calls[0]['headers']['Authorization'] == 'Bearer pat-test'
    assert result.metadata['parsed_response']['next_cursor'] == '2' and result.metadata['parsed_response']['resource_count'] == 1


def test_live_write_remains_fail_closed_before_network(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault = provider_map()['hubspot'], InMemorySecretVault()
    _put(vault, provider, 'hub-a', 'private_app_token', 'pat-test')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: (_ for _ in ()).throw(AssertionError('network called')))
    result = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='hub-a', operation='task_create', mode='live', payload={})
    assert result.status == 'rejected_provider_write_guard' and result.accepted is False


def test_only_proven_read_providers_receive_live_network_binding() -> None:
    transports = build_live_http_transports(InMemorySecretVault(), bind_live_network=True)
    assert transports['telegram_bot'].bind_live_network is True and transports['hubspot'].bind_live_network is True
    assert all(not transport.bind_live_network for key, transport in transports.items() if key not in {'telegram_bot', 'hubspot'})
