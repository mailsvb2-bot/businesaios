from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime._internal.http_transport import SyncHTTPResult
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry
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
    assert result.status == 'probe_live_ok' and result.ok is True and calls[0]['url'] == 'https://api.telegram.org/bot123:abc/getMe' and calls[0]['method'] == 'GET'


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
    assert all(transports[key].bind_live_network is True for key in {'telegram_bot', 'hubspot', 'vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging'})
    assert all(not transport.bind_live_network for key, transport in transports.items() if key not in {'telegram_bot', 'hubspot', 'vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging'})


def test_vk_live_probe_uses_official_post_form_without_exposing_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['vk_messaging'], InMemorySecretVault(), []
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'vk-token', 'group_id': '123'}.items():
        _put(vault, provider, 'biz-a', name, value)
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"response":[{"id":123}]}')))
    result = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    assert result.status == 'probe_live_ok' and result.ok is True
    assert calls[0]['method'] == 'POST' and calls[0]['url'] == 'https://api.vk.com/method/groups.getById'
    assert b'access_token=vk-token' in calls[0]['body'] and b'group_id=123' in calls[0]['body'] and b'v=5.199' in calls[0]['body']
    assert result.metadata['response']['request']['form_body']['access_token'] == '***'


def test_vk_live_read_uses_messages_get_conversations_and_write_stays_fail_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['vk_messaging'], InMemorySecretVault(), []
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'vk-token', 'group_id': '123'}.items():
        _put(vault, provider, 'biz-a', name, value)
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"response":{"count":0,"items":[]}}')))
    runtime = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True))
    read = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={'count': 10})
    assert read.status == 'live_executed' and calls[0]['url'].endswith('/messages.getConversations') and b'count=10' in calls[0]['body']
    before = len(calls)
    write = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', mode='live', payload={'peer_id': 42, 'text': 'no'})
    assert write.status == 'rejected_provider_write_guard' and len(calls) == before


def test_max_live_probe_and_read_use_api2_raw_authorization(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['max_messaging'], InMemorySecretVault(), []
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'max-token'}.items():
        _put(vault, provider, 'biz-a', name, value)
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"messages":[]}')))
    probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    assert probe.status == 'probe_live_ok' and calls[0]['url'] == 'https://platform-api2.max.ru/me'
    assert calls[0]['headers']['Authorization'] == 'max-token'
    runtime = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True))
    read = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={'message_ids': ['m1', 'm2']})
    assert read.status == 'live_executed' and calls[1]['url'] == 'https://platform-api2.max.ru/messages?message_ids=m1%2Cm2'
    assert calls[1]['method'] == 'GET' and read.metadata['transport_response']['request']['headers']['Authorization'] == '***'


def test_vk_max_live_health_requires_native_token_but_bridge_dry_run_does_not() -> None:
    for key in ('vk_messaging', 'max_messaging'):
        provider, vault = provider_map()[key], InMemorySecretVault()
        _put(vault, provider, 'biz-a', 'webhook_secret', 'bridge-secret')
        health = ProviderConnectorHealthService(vault)
        dry = health.probe(provider=provider, tenant_id='tenant-a', business_id='biz-a', probe_mode='dry_run')
        live = health.probe(provider=provider, tenant_id='tenant-a', business_id='biz-a', probe_mode='live')
        assert dry.status == 'ready_for_credentials'
        assert live.status == 'misconfigured' and live.reason == 'missing_required_secrets'
        assert live.metadata['missing_fields'] == ('access_token',)


def test_vk_api_error_body_fails_live_probe_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault = provider_map()['vk_messaging'], InMemorySecretVault()
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'vk-token', 'group_id': '123'}.items():
        _put(vault, provider, 'biz-a', name, value)
    failure = SyncHTTPResult(status=200, headers={}, json={}, text='{"error":{"error_code":5,"error_msg":"User authorization failed"}}')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: failure)
    probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    read = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={})
    assert probe.status == 'probe_live_failed' and probe.ok is False
    assert read.status == 'live_execution_failed' and read.accepted is False
    assert read.metadata['parsed_response']['error_code'] == '5'
    rate_limited = ProviderResponseParsers().parse(provider=provider, operation='message_send', response={'http_status': 200, 'response_body': '{"error":{"error_code":6,"error_msg":"Too many requests"}}'})
    assert rate_limited['error_category'] == 'rate_limit' and rate_limited['retryable'] is True and rate_limited['delivery_state'] == 'rejected'


def test_max_http_error_fails_live_probe_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault = provider_map()['max_messaging'], InMemorySecretVault()
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'max-token'}.items():
        _put(vault, provider, 'biz-a', name, value)
    failure = SyncHTTPResult(status=429, headers={}, json={}, text='{"code":"too_many_requests","message":"slow down"}', error_kind='http_error', error_message='429')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: failure)
    probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    read = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={'chat_id': '1'})
    assert probe.status == 'probe_live_failed' and probe.ok is False
    assert read.status == 'live_execution_failed' and read.accepted is False
    assert read.metadata['parsed_response']['error_category'] == 'rate_limit' and read.metadata['parsed_response']['retryable'] is True
    assert read.metadata['retry_policy']['retryable'] is True and read.metadata['retry_policy']['next_delay_seconds'] == 30
    assert 'scheduled_retry' not in read.metadata


def test_vk_max_live_probe_updates_channel_health_registry(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    for key in ('vk_messaging', 'max_messaging'):
        provider, vault, registry = provider_map()[key], InMemorySecretVault(), ChannelHealthRegistry()
        for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'token'}.items():
            _put(vault, provider, 'biz-a', name, value)
        monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: SyncHTTPResult(status=200, headers={}, json={}, text='{}'))
        result = ProviderLiveProbeRuntime(vault, channel_health_registry=registry).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
        assert provider.messaging_live_probe_supported is True and result.status == 'probe_live_ok'
        assert registry.get(provider.messaging_channel).healthy is True


def test_vk_live_send_requires_runtime_approval_marker(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['vk_messaging'], InMemorySecretVault(), []
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'vk-token', 'group_id': '123'}.items():
        _put(vault, provider, 'biz-a', name, value)
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"response":777}')))
    transport = build_live_http_transports(vault, bind_live_network=True)['vk_messaging']
    blocked = transport.execute(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', payload={'peer_id': 42, 'text': 'hello', 'random_id': 7, '_allow_network': True})
    assert blocked['_prepared_only'] is True and calls == []
    sent = transport.execute(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', payload={'peer_id': 42, 'text': 'hello', 'random_id': 7, '_allow_network': True, '_provider_write_approved': True})
    assert sent['_response_ok'] is True and calls[0]['url'] == 'https://api.vk.com/method/messages.send' and calls[0]['method'] == 'POST'
    assert b'peer_id=42' in calls[0]['body'] and b'message=hello' in calls[0]['body'] and b'random_id=7' in calls[0]['body']
    assert b'_approval' not in calls[0]['body'] and b'_provider_write_approved' not in calls[0]['body']


def test_max_live_send_requires_runtime_approval_marker(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault, calls = provider_map()['max_messaging'], InMemorySecretVault(), []
    for name, value in {'webhook_secret': 'bridge-secret', 'access_token': 'max-token'}.items():
        _put(vault, provider, 'biz-a', name, value)
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"message":{"body":{"mid":"m1"}}}')))
    transport = build_live_http_transports(vault, bind_live_network=True)['max_messaging']
    blocked = transport.execute(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', payload={'chat_id': 99, 'text': 'hello', '_allow_network': True})
    assert blocked['_prepared_only'] is True and calls == []
    sent = transport.execute(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', payload={'chat_id': 99, 'text': 'hello', '_approval': {'approval_id': 'secret-internal'}, '_allow_network': True, '_provider_write_approved': True})
    assert sent['_response_ok'] is True and calls[0]['url'] == 'https://platform-api2.max.ru/messages?chat_id=99' and calls[0]['method'] == 'POST'
    assert calls[0]['headers']['Authorization'] == 'max-token' and calls[0]['body'] == b'{"text": "hello"}'
    assert b'_approval' not in calls[0]['body'] and b'_provider_write_approved' not in calls[0]['body']


def test_slack_discord_live_probe_and_read_use_native_bot_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    cases = {
        'slack_messaging': ('xoxb-test', 'https://slack.com/api/auth.test', 'https://slack.com/api/conversations.history?channel=C123', 'Bearer xoxb-test', {'channel_id': 'C123'}),
        'discord_messaging': ('discord-test', 'https://discord.com/api/v10/users/@me', 'https://discord.com/api/v10/channels/123/messages', 'Bot discord-test', {'channel_id': '123'}),
    }
    for key, (token, probe_url, read_url, auth, read_payload) in cases.items():
        provider, vault, calls = provider_map()[key], InMemorySecretVault(), []
        _put(vault, provider, 'biz-a', 'webhook_secret', 'bridge-secret')
        _put(vault, provider, 'biz-a', 'bot_token', token)
        monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{}')))
        probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
        assert probe.status == 'probe_live_ok' and calls[0]['url'] == probe_url and calls[0]['headers']['Authorization'] == auth
        runtime = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True))
        read = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload=read_payload)
        assert read.status == 'live_executed' and calls[1]['url'] == read_url and calls[1]['method'] == 'GET'
        assert read.metadata['transport_response']['request']['headers']['Authorization'] == '***'


def test_slack_discord_direct_send_stays_prepared_only_even_with_internal_write_marker(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: (_ for _ in ()).throw(AssertionError('network called')))
    for key, payload in (('slack_messaging', {'channel_id': 'C123', 'text': 'hello'}), ('discord_messaging', {'channel_id': '123', 'text': 'hello'})):
        provider, vault = provider_map()[key], InMemorySecretVault()
        _put(vault, provider, 'biz-a', 'webhook_secret', 'bridge-secret')
        _put(vault, provider, 'biz-a', 'bot_token', 'token')
        result = build_live_http_transports(vault, bind_live_network=True)[key].execute(
            provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send',
            payload={**payload, '_allow_network': True, '_provider_write_approved': True},
        )
        assert result['_prepared_only'] is True



def test_slack_discord_live_read_missing_channel_fails_closed_before_network(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: (_ for _ in ()).throw(AssertionError('network called')))
    for key in ('slack_messaging', 'discord_messaging'):
        provider, vault = provider_map()[key], InMemorySecretVault()
        _put(vault, provider, 'biz-a', 'webhook_secret', 'bridge-secret')
        _put(vault, provider, 'biz-a', 'bot_token', 'token')
        result = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(
            provider=provider,
            tenant_id='tenant-a',
            business_id='biz-a',
            operation='message_read',
            mode='live',
            payload={},
        )
        assert result.status == 'live_prepared_only' and result.accepted is False
        assert result.metadata['transport_response']['reason'] == 'native_message_read_payload_invalid'


def test_slack_live_http_200_logical_error_fails_probe_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault = provider_map()['slack_messaging'], InMemorySecretVault()
    _put(vault, provider, 'biz-a', 'webhook_secret', 'bridge-secret')
    _put(vault, provider, 'biz-a', 'bot_token', 'xoxb-invalid')
    failure = SyncHTTPResult(status=200, headers={}, json={}, text='{"ok":false,"error":"invalid_auth"}')
    monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **_kwargs: failure)

    probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    read = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(
        provider=provider,
        tenant_id='tenant-a',
        business_id='biz-a',
        operation='message_read',
        mode='live',
        payload={'channel_id': 'C123'},
    )

    assert probe.status == 'probe_live_failed' and probe.ok is False
    assert read.status == 'live_execution_failed' and read.accepted is False
    assert read.metadata['parsed_response']['ok'] is False
    assert read.metadata['parsed_response']['error_code'] == 'invalid_auth'



def test_live_read_requires_explicit_binding_readiness_even_when_transport_is_bound(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    provider, vault = provider_map()['email_connector'], InMemorySecretVault()
    runtime = ProviderLiveSyncRuntime(vault, transports={'email_connector': object()})
    runner = runtime.describe_runner(provider)
    assert runner['transport_bound'] is True and runner['live_read_supported'] is False
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={})
    assert result.status == 'live_read_unsupported' and result.accepted is False
    assert result.metadata['reason'] == 'live_read_transport_not_ready'
