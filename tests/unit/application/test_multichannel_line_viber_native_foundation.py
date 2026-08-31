from __future__ import annotations

import base64
import hashlib
import hmac
import json

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from application.public_site.cta_intake import public_integration_marketplace
from runtime._internal.http_transport import SyncHTTPResult
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRef
from security.secret_vault import InMemorySecretVault


def _put(vault: InMemorySecretVault, provider, name: str, value: str) -> None:
    vault.seed_plaintext(
        ref=SecretRef(
            tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a',
            secret_name=f'{provider.connector_id}.{name}',
        ),
        plaintext=value,
    )


def test_line_viber_native_credentials_extend_bridge_without_replacing_it() -> None:
    providers = provider_map()
    expected = {
        'line_messaging': ('channel_access_token', 'channel_secret'),
        'viber_messaging': ('auth_token', 'sender_name'),
    }
    for key, native_fields in expected.items():
        provider = providers[key]
        fields = {field.secret_name: field for field in provider.secret_fields}
        assert fields['webhook_secret'].required is True
        assert all(fields[name].required is False for name in native_fields)
        assert provider.messaging_live_probe_supported is True
        binding = provider_transport_binding_for_key(key)
        assert binding['live_probe_ready'] is True
        assert binding['live_read_ready'] is False
        assert binding['live_ready'] is False
        truth = provider_truth_map()[key]
        assert truth.write_supported is False and truth.live_ready is False


def test_line_native_signature_uses_raw_body_and_cannot_downgrade_to_bridge() -> None:
    provider, vault = provider_map()['line_messaging'], InMemorySecretVault()
    _put(vault, provider, 'webhook_secret', 'bridge-secret')
    _put(vault, provider, 'channel_secret', 'line-channel-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"destination":"U1","events":[{"type":"message","webhookEventId":"evt-line-1","source":{"userId":"U2"},"message":{"id":"m1","type":"text","text":"hello"}}]}'
    signature = base64.b64encode(hmac.new(b'line-channel-secret', body, hashlib.sha256).digest()).decode('ascii')
    assert runtime.describe(provider).verification_kind == 'line_hmac_sha256_base64_or_shared_secret'
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Line-Signature': signature}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Line-Signature': signature}, body=body + b' ') is False
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Line-Signature': '   ', 'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is False
    missing_native = InMemorySecretVault(); _put(missing_native, provider, 'webhook_secret', 'bridge-secret')
    assert ProviderWebhookRuntime(missing_native).verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Line-Signature': signature, 'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is False


def test_viber_native_signature_uses_auth_token_and_cannot_downgrade_to_bridge() -> None:
    provider, vault = provider_map()['viber_messaging'], InMemorySecretVault()
    _put(vault, provider, 'webhook_secret', 'bridge-secret')
    _put(vault, provider, 'auth_token', 'viber-auth-token')
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"event":"message","timestamp":1457764197627,"message_token":4912661846655238145,"sender":{"id":"v-user"},"message":{"type":"text","text":"hello"}}'
    signature = hmac.new(b'viber-auth-token', body, hashlib.sha256).hexdigest()
    assert runtime.describe(provider).verification_kind == 'viber_hmac_sha256_hex_or_shared_secret'
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Viber-Content-Signature': signature}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Viber-Content-Signature': 'bad', 'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is False
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Viber-Content-Signature': '', 'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'}, body=body) is False


def test_line_viber_webhook_identity_uses_vendor_event_ids_for_canonical_idempotency() -> None:
    normalizer, routes, providers = ProviderPayloadNormalizers(), ProviderWebhookRouteRegistry(), provider_map()
    line_body = json.dumps({'events': [{'type': 'message', 'webhookEventId': 'evt-line-1', 'source': {'userId': 'U1'}, 'message': {'id': 'm-line', 'text': 'hello'}}]}).encode()
    viber_body = json.dumps({'event': 'message', 'message_token': 991, 'sender': {'id': 'V1'}, 'message': {'text': 'hello'}}).encode()
    line = normalizer.normalize_webhook_payload(provider=providers['line_messaging'], headers={}, body=line_body)
    viber = normalizer.normalize_webhook_payload(provider=providers['viber_messaging'], headers={}, body=viber_body)
    assert line == {'topic': 'message', 'source_ref': 'U1', 'resource_id': 'evt-line-1', 'event_key_hint': 'evt-line-1'}
    assert viber == {'topic': 'message', 'source_ref': 'V1', 'resource_id': '991', 'event_key_hint': '991'}
    assert routes.extract(providers['line_messaging'], {}, line_body)['event_key'] == 'evt-line-1'
    assert routes.extract(providers['viber_messaging'], {}, viber_body)['event_key'] == '991'


def test_line_viber_prepared_outbound_matches_vendor_shape_but_remains_non_live() -> None:
    providers, transports = provider_map(), build_provider_vendor_transports()
    line = transports['line_messaging'].execute(provider=providers['line_messaging'], tenant_id='t', business_id='b', operation='message_send', payload={'user_id': 'U1', 'text': 'hello'})['request']
    viber = transports['viber_messaging'].execute(provider=providers['viber_messaging'], tenant_id='t', business_id='b', operation='message_send', payload={'user_id': 'V1', 'sender_name': 'Owner', 'text': 'hello'})['request']
    assert line == {'method': 'POST', 'url_template': 'https://api.line.me/v2/bot/message/push', 'headers': {'Authorization': 'Bearer {channel_access_token}'}, 'json_body': {'to': 'U1', 'messages': [{'type': 'text', 'text': 'hello'}]}}
    assert viber == {'method': 'POST', 'url_template': 'https://chatapi.viber.com/pa/send_message', 'headers': {'X-Viber-Auth-Token': '{auth_token}'}, 'json_body': {'receiver': 'V1', 'type': 'text', 'sender': {'name': 'Owner'}, 'text': 'hello'}}
    vault = InMemorySecretVault(); _put(vault, providers['viber_messaging'], 'auth_token', 'viber-token'); _put(vault, providers['viber_messaging'], 'sender_name', 'Configured Owner')
    prepared = build_live_http_transports(vault, bind_live_network=False)['viber_messaging'].execute(provider=providers['viber_messaging'], tenant_id='tenant-a', business_id='business-a', operation='message_send', payload={'user_id': 'V1', 'text': 'hello'})['request']
    assert prepared['json_body']['sender']['name'] == 'Configured Owner'
    for key in ('line_messaging', 'viber_messaging'):
        assert provider_truth_map()[key].write_supported is False


def test_line_viber_live_health_uses_official_probe_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    cases = {
        'line_messaging': ('channel_access_token', 'line-token', 'GET', 'https://api.line.me/v2/bot/info', 'Authorization', 'Bearer line-token', '{"userId":"U1","displayName":"Bot"}'),
        'viber_messaging': ('auth_token', 'viber-token', 'POST', 'https://chatapi.viber.com/pa/get_account_info', 'X-Viber-Auth-Token', 'viber-token', '{"status":0,"status_message":"ok","id":"pa:1"}'),
    }
    for key, (field, token, method, url, header, auth, response_body) in cases.items():
        provider, vault, calls = provider_map()[key], InMemorySecretVault(), []
        _put(vault, provider, 'webhook_secret', 'bridge-secret'); _put(vault, provider, field, token)
        monkeypatch.setattr('runtime.business_autonomy.provider_http_live_clients._sync_request', lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text=response_body)))
        probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id='tenant-a', business_id='business-a', mode='live')
        assert probe.status == 'probe_live_ok' and probe.ok is True
        assert calls[0]['method'] == method and calls[0]['url'] == url and calls[0]['headers'][header] == auth
        public_headers = probe.metadata['response']['request']['headers']
        assert public_headers[header] == '***'
        before = len(calls)
        read = ProviderLiveSyncRuntime(vault, transports=build_live_http_transports(vault, bind_live_network=True)).run(provider=provider, tenant_id='tenant-a', business_id='business-a', operation='message_read', mode='live', payload={})
        assert read.status == 'live_read_unsupported' and read.accepted is False and len(calls) == before


def test_line_viber_live_probe_requires_native_token_while_bridge_dry_run_survives() -> None:
    for key, field in (('line_messaging', 'channel_access_token'), ('viber_messaging', 'auth_token')):
        provider, vault = provider_map()[key], InMemorySecretVault()
        _put(vault, provider, 'webhook_secret', 'bridge-secret')
        health = ProviderConnectorHealthService(vault)
        assert health.probe(provider=provider, tenant_id='tenant-a', business_id='business-a', probe_mode='dry_run').status == 'ready_for_credentials'
        live = health.probe(provider=provider, tenant_id='tenant-a', business_id='business-a', probe_mode='live')
        assert live.status == 'misconfigured' and live.metadata['missing_fields'] == (field,)


def test_viber_http_200_nonzero_status_is_logical_failure() -> None:
    parser = ProviderResponseParsers(); provider = provider_map()['viber_messaging']
    ok = parser.parse(provider=provider, operation='health_probe', response={'http_status': 200, 'response_body': '{"status":0,"status_message":"ok","id":"pa:1"}'})
    failed = parser.parse(provider=provider, operation='health_probe', response={'http_status': 200, 'response_body': '{"status":2,"status_message":"invalidAuthToken"}'})
    assert ok['ok'] is True and ok['error_code'] is None
    assert failed['ok'] is False and failed['error_code'] == '2'


def test_marketplace_reports_native_plus_bridge_without_write_claim() -> None:
    rows = {row['provider_key']: row for row in public_integration_marketplace()}
    assert rows['line_messaging']['connection_mode'] == 'native_line_messaging_api_or_provider_webhook_bridge'
    assert rows['viber_messaging']['connection_mode'] == 'native_viber_bot_api_or_provider_webhook_bridge'
    assert rows['line_messaging']['write_supported'] is False
    assert rows['viber_messaging']['write_supported'] is False
