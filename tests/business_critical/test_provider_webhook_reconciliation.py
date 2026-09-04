from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import parse_qs

import runtime.business_autonomy.provider_webhook_reconciliation as sut
from application.business_autonomy.provider_catalog import provider_map
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
