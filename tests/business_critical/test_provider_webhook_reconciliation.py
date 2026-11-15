from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from types import SimpleNamespace
from urllib.parse import parse_qs

import runtime.business_autonomy.provider_webhook_reconciliation as sut
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_transport_bindings import max_tls_ca_file
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, business_id: str, name: str, value: str) -> None:
    ref = SecretRef(
        tenant_id='tenant-a', connector_id=provider.connector_id, scope=business_id,
        secret_name=f'{provider.connector_id}.{name}',
    )
    vault.put(
        SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR),
        plaintext=value.encode(),
    )


def _response(payload, status: int = 200):
    return SimpleNamespace(status=status, json=payload, text=json.dumps(payload), error_kind=None)


def test_telegram_reconcile_generates_separate_webhook_secret(monkeypatch) -> None:
    provider = provider_map()['telegram_bot']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-a', 'bot_token', '123:BOT')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    calls = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        if str(kwargs['url']).endswith('/getWebhookInfo'):
            return _response({'ok': True, 'result': {'url': 'https://api.businessaios.ru/providers/webhook/tenant-a/biz-a/telegram_bot', 'pending_update_count': 2}})
        return _response({'ok': True, 'result': True})

    monkeypatch.setattr(sut, '_sync_request', fake_request)
    result = sut.ProviderWebhookReconciler(vault).reconcile(
        provider=provider, tenant_id='tenant-a', business_id='biz-a'
    )
    assert result.ready is True and result.status == 'reconciled'
    secret = sut.ProviderWebhookReconciler(vault)._secret(provider, 'tenant-a', 'biz-a', 'webhook_secret')
    assert secret and secret != '123:BOT'
    post_payload = json.loads(next(call['body'] for call in calls if str(call['url']).endswith('/setWebhook')).decode())
    assert post_payload['secret_token'] == secret
    assert post_payload['url'].endswith('/providers/webhook/tenant-a/biz-a/telegram_bot')
    contract = ProviderWebhookRuntime(vault).describe(provider)
    assert contract.metadata['secret_field'] == 'webhook_secret'


def test_vk_reconcile_derives_confirmation_and_reconciles_server(monkeypatch) -> None:
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    for name, value in {'access_token': 'vk-token', 'group_id': '42', 'webhook_secret': 'vk-hook'}.items():
        _put(vault, provider, 'biz-vk', name, value)
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    seen_methods = []

    def fake_request(**kwargs):
        params = parse_qs(bytes(kwargs.get('body') or b'').decode())
        method = str(kwargs['url']).rsplit('/', 1)[-1]
        seen_methods.append((method, params))
        if method == 'groups.getCallbackConfirmationCode':
            return _response({'response': {'code': 'confirm-42'}})
        if method == 'groups.addCallbackServer':
            return _response({'response': {'server_id': 7}})
        if method == 'groups.setCallbackSettings':
            return _response({'response': 1})
        if method == 'groups.getCallbackServers':
            count = sum(1 for item, _ in seen_methods if item == method)
            if count == 1:
                return _response({'response': {'items': []}})
            return _response({'response': {'items': [{'id': 7, 'url': 'https://api.businessaios.ru/providers/webhook/tenant-a/biz-vk/vk_messaging'}]}})
        raise AssertionError(method)

    monkeypatch.setattr(sut, '_sync_request', fake_request)
    result = sut.ProviderWebhookReconciler(vault).reconcile(
        provider=provider, tenant_id='tenant-a', business_id='biz-vk'
    )
    assert result.ready is True
    assert result.metadata['server_id'] == 7
    assert result.metadata['event_types'] == ('message_new', 'message_event')
    assert sut.ProviderWebhookReconciler(vault)._secret(provider, 'tenant-a', 'biz-vk', 'confirmation_code') == 'confirm-42'
    settings = next(params for method, params in seen_methods if method == 'groups.setCallbackSettings')
    assert settings['message_new'] == ['1'] and settings['message_event'] == ['1']


def test_max_reconcile_rewrites_subscription_and_verifies(monkeypatch) -> None:
    provider = provider_map()['max_messaging']
    vault = InMemorySecretVault()
    for name, value in {'access_token': 'max-token', 'webhook_secret': 'max-hook'}.items():
        _put(vault, provider, 'biz-max', name, value)
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    calls = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        if kwargs['method'] == 'POST':
            return _response({'success': True})
        get_count = sum(1 for call in calls if call['method'] == 'GET')
        if get_count == 1:
            return _response({'subscriptions': [{'url': 'https://stale.example/hook'}]})
        return _response({'subscriptions': [{'url': 'https://api.businessaios.ru/providers/webhook/tenant-a/biz-max/max_messaging'}]})

    monkeypatch.setattr(sut, '_sync_request', fake_request)
    result = sut.ProviderWebhookReconciler(vault).reconcile(
        provider=provider, tenant_id='tenant-a', business_id='biz-max'
    )
    assert result.ready is True and result.metadata['subscription_visible'] is True
    post = next(call for call in calls if call['method'] == 'POST')
    body = json.loads(post['body'].decode())
    assert body['secret'] == 'max-hook'
    assert body['update_types'] == ['message_created', 'message_callback', 'bot_started']


def test_reconcile_without_public_base_is_explicit_manual_required(monkeypatch) -> None:
    provider = provider_map()['max_messaging']
    vault = InMemorySecretVault()
    monkeypatch.delenv('PUBLIC_BASE_URL', raising=False)
    result = sut.ProviderWebhookReconciler(vault).reconcile(
        provider=provider, tenant_id='tenant-a', business_id='biz-a'
    )
    assert result.status == 'manual_required'
    assert result.ready is False
    assert result.metadata['reason'] == 'public_base_url_not_configured'


def test_reconcile_rejects_non_https_public_base(monkeypatch) -> None:
    provider = provider_map()['telegram_bot']
    monkeypatch.setenv('PUBLIC_BASE_URL', 'http://internal.invalid')
    try:
        sut.ProviderWebhookReconciler(InMemorySecretVault()).reconcile(
            provider=provider, tenant_id='tenant-a', business_id='biz-a'
        )
    except ValueError as exc:
        assert 'HTTPS' in str(exc)
    else:
        raise AssertionError('non-HTTPS public base must fail closed')


def test_telegram_http_200_application_rejection_fails_closed(monkeypatch) -> None:
    provider = provider_map()['telegram_bot']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-a', 'bot_token', '123:BOT')
    _put(vault, provider, 'biz-a', 'webhook_secret', 'hook-secret')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    monkeypatch.setattr(
        sut,
        '_sync_request',
        lambda **_kwargs: _response({'ok': False, 'description': 'rejected'}),
    )
    try:
        sut.ProviderWebhookReconciler(vault).reconcile(
            provider=provider, tenant_id='tenant-a', business_id='biz-a'
        )
    except RuntimeError as exc:
        assert 'set_webhook_rejected' in str(exc)
    else:
        raise AssertionError('Telegram application rejection must fail closed')


def test_max_http_200_application_rejection_fails_closed(monkeypatch) -> None:
    provider = provider_map()['max_messaging']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-max', 'access_token', 'max-token')
    _put(vault, provider, 'biz-max', 'webhook_secret', 'max-hook')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    calls = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        if kwargs['method'] == 'GET':
            return _response({'subscriptions': []})
        return _response({'success': False, 'message': 'rejected'})

    monkeypatch.setattr(sut, '_sync_request', fake_request)
    try:
        sut.ProviderWebhookReconciler(vault).reconcile(
            provider=provider, tenant_id='tenant-a', business_id='biz-max'
        )
    except RuntimeError as exc:
        assert 'subscription_rejected' in str(exc)
    else:
        raise AssertionError('MAX application rejection must fail closed')


def test_vk_existing_callback_server_rewrites_current_secret(monkeypatch) -> None:
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    for name, value in {'access_token': 'vk-token', 'group_id': '42', 'webhook_secret': 'rotated-hook'}.items():
        _put(vault, provider, 'biz-vk', name, value)
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    seen = []
    target = 'https://api.businessaios.ru/providers/webhook/tenant-a/biz-vk/vk_messaging'

    def fake_request(**kwargs):
        params = parse_qs(bytes(kwargs.get('body') or b'').decode())
        method = str(kwargs['url']).rsplit('/', 1)[-1]
        seen.append((method, params))
        if method == 'groups.getCallbackConfirmationCode':
            return _response({'response': {'code': 'confirm-42'}})
        if method == 'groups.getCallbackServers':
            return _response({'response': {'items': [{'id': 9, 'url': target}]}})
        if method in {'groups.editCallbackServer', 'groups.setCallbackSettings'}:
            return _response({'response': 1})
        raise AssertionError(method)
    monkeypatch.setattr(sut, '_sync_request', fake_request)
    result = sut.ProviderWebhookReconciler(vault).reconcile(
        provider=provider, tenant_id='tenant-a', business_id='biz-vk'
    )
    assert result.ready is True
    edited = next(params for method, params in seen if method == 'groups.editCallbackServer')
    assert edited['server_id'] == ['9']
    assert edited['secret_key'] == ['rotated-hook']
    assert edited['url'] == [target]
    assert not any(method == 'groups.addCallbackServer' for method, _ in seen)

"""MAX API trust cannot be replaced by a global TLS bypass."""






def test_max_ca_is_opt_in_and_never_changes_other_hosts(monkeypatch):
    monkeypatch.delenv('BUSINESAIOS_MAX_CA_FILE', raising=False)
    assert max_tls_ca_file('https://platform-api2.max.ru/me') is None
    assert max_tls_ca_file('https://api.vk.com/method/messages.send') is None


def test_max_ca_fail_closed_on_foreign_host(monkeypatch, tmp_path):
    cert = tmp_path / 'root.pem'
    cert.write_text('not-a-cert')
    monkeypatch.setenv('BUSINESAIOS_MAX_CA_FILE', str(cert))
    for url in ('https://api.vk.com/method/messages.send', 'http://platform-api2.max.ru/me', 'https://platform-api2.max.ru.evil.example/me', 'https://platform-api2.max.ru:444/me'):
        with pytest.raises(ValueError, match='origin_denied'):
            max_tls_ca_file(url)


def test_max_ca_refuses_bad_certificate_even_on_correct_host(monkeypatch, tmp_path):
    cert = tmp_path / 'root.pem'
    cert.write_text('-----BEGIN CERTIFICATE-----\nYQ==\n-----END CERTIFICATE-----\n')
    monkeypatch.setenv('BUSINESAIOS_MAX_CA_FILE', str(cert))
    with pytest.raises(ValueError, match='untrusted_fingerprint'):
        max_tls_ca_file('https://platform-api2.max.ru/me')


def test_authenticated_tls_context_uses_default_trust_and_hostname_verification(monkeypatch, tmp_path):
    import runtime._internal.http_transport as transport
    observed = {}
    class DummyContext:
        def load_verify_locations(self, *, cafile):
            observed['file'] = cafile
        check_hostname = True
        verify_mode = 2
    class FakeOpener:
        def __init__(self, *handlers):
            observed['handlers'] = handlers
        def open(self, request, *, timeout):
            observed['called'] = True
            raise OSError('offline test')
    monkeypatch.setattr(transport.ssl, 'create_default_context', lambda: DummyContext())
    monkeypatch.setattr(transport._urllib_request(), 'build_opener', lambda *handlers: FakeOpener(*handlers))
    result = transport.sync_request(method='GET', url='https://platform-api2.max.ru/me', headers={'Authorization': 'test-token'}, tls_ca_file='/secure/max/root.pem')
    assert observed['file'] == '/secure/max/root.pem'
    assert any(getattr(handler, '_context', None) is not None for handler in observed['handlers'])
    assert result.error_kind == 'transport_error'

def _signed_hub_headers(secret: str, body: bytes) -> dict[str, str]:
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return {'X-Hub-Signature-256': f'sha256={signature}'}


def test_whatsapp_webhook_requires_the_configured_phone_number_id() -> None:
    provider = provider_map()['whatsapp_cloud']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-wa', 'app_secret', 'meta-app-secret')
    _put(vault, provider, 'biz-wa', 'phone_number_id', 'phone-123')
    runtime = ProviderWebhookRuntime(vault)

    def body_for(phone_number_id: str) -> bytes:
        return json.dumps({
            'object': 'whatsapp_business_account',
            'entry': [{
                'id': 'waba-1',
                'changes': [{
                    'field': 'messages',
                    'value': {
                        'metadata': {'phone_number_id': phone_number_id, 'display_phone_number': '+15550001111'},
                        'messages': [{'from': '15550002222', 'id': 'wamid-1', 'text': {'body': 'hello'}}],
                    },
                }],
            }],
        }).encode()

    valid = body_for('phone-123')
    wrong_recipient = body_for('phone-999')
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-wa',
        headers=_signed_hub_headers('meta-app-secret', valid), body=valid,
    ) is True
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-wa',
        headers=_signed_hub_headers('meta-app-secret', wrong_recipient), body=wrong_recipient,
    ) is False


@pytest.mark.parametrize(
    ('provider_key', 'recipient_secret', 'account_id'),
    (
        ('instagram_messaging', 'ig_user_id', 'ig-account-123'),
        ('messenger_messaging', 'page_id', 'page-123'),
    ),
)
def test_meta_messaging_webhook_requires_the_configured_account_id(
    provider_key: str, recipient_secret: str, account_id: str,
) -> None:
    provider = provider_map()[provider_key]
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-meta', 'app_secret', 'meta-app-secret')
    _put(vault, provider, 'biz-meta', recipient_secret, account_id)
    runtime = ProviderWebhookRuntime(vault)

    def body_for(observed_id: str) -> bytes:
        return json.dumps({
            'object': 'page',
            'entry': [{
                'id': observed_id,
                'time': 1710000000,
                'messaging': [{
                    'sender': {'id': 'customer-1'},
                    'recipient': {'id': observed_id},
                    'message': {'mid': 'message-1', 'text': 'hello'},
                }],
            }],
        }).encode()

    valid = body_for(account_id)
    wrong_recipient = body_for('other-account')
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-meta',
        headers=_signed_hub_headers('meta-app-secret', valid), body=valid,
    ) is True
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-meta',
        headers=_signed_hub_headers('meta-app-secret', wrong_recipient), body=wrong_recipient,
    ) is False


def test_vk_webhook_requires_the_configured_group_id_and_business_scope() -> None:
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-vk', 'webhook_secret', 'vk-hook-secret')
    _put(vault, provider, 'biz-vk', 'group_id', '42')
    runtime = ProviderWebhookRuntime(vault)
    body = json.dumps({
        'type': 'message_new',
        'group_id': 42,
        'event_id': 'vk-event-1',
        'object': {'message': {'from_id': 7, 'peer_id': 7, 'text': 'hello'}},
    }).encode()
    headers = {'X-BusinessAIOS-Webhook-Secret': 'vk-hook-secret'}
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-vk',
        headers=headers, body=body,
    ) is True
    wrong_group = json.dumps({'type': 'message_new', 'group_id': 99, 'event_id': 'vk-event-2'}).encode()
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-vk',
        headers={'X-BusinessAIOS-Webhook-Secret': 'vk-hook-secret'}, body=wrong_group,
    ) is False
    assert runtime.verify(
        provider=provider, tenant_id='tenant-b', business_id='biz-vk',
        headers=headers, body=body,
    ) is False
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='other-business',
        headers=headers, body=body,
    ) is False


def test_vk_webhook_fails_closed_when_group_binding_is_missing() -> None:
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    _put(vault, provider, 'biz-vk', 'webhook_secret', 'vk-hook-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = json.dumps({'type': 'message_new', 'group_id': 42, 'event_id': 'vk-event-1'}).encode()
    assert runtime.verify(
        provider=provider, tenant_id='tenant-a', business_id='biz-vk',
        headers={'X-BusinessAIOS-Webhook-Secret': 'vk-hook-secret'}, body=body,
    ) is False

