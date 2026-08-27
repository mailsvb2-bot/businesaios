from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, name: str, value: str) -> None:
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.{name}')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=value.encode())


def test_vk_and_max_keep_bridge_onboarding_while_exposing_native_credentials() -> None:
    providers = provider_map()
    vk = {field.secret_name: field for field in providers['vk_messaging'].secret_fields}
    max_fields = {field.secret_name: field for field in providers['max_messaging'].secret_fields}
    assert vk['webhook_secret'].required is True and vk['access_token'].required is False and vk['group_id'].required is False
    assert max_fields['webhook_secret'].required is True and max_fields['access_token'].required is False
    assert all('message_send' in ProviderSyncRuntimePlanner().describe(providers[key]).write_operations for key in ('vk_messaging', 'max_messaging'))


def test_vk_prepared_native_transport_uses_api_519_and_messages_send() -> None:
    provider = provider_map()['vk_messaging']
    result = build_provider_vendor_transports()['vk_messaging'].execute(provider=provider, tenant_id='tenant-a', business_id='business-a', operation='message_send', payload={'peer_id': 42, 'text': 'hello', 'random_id': 7, 'group_id': 123})
    request = result['request']
    assert request['url_template'] == 'https://api.vk.com/method/messages.send'
    assert request['form_body'] == {'peer_id': '42', 'random_id': 7, 'message': 'hello', 'group_id': '123', 'access_token': '{access_token}', 'v': '5.199'}
    assert result['_prepared_only'] is True and result['transport_binding']['live_ready'] is True


def test_max_prepared_native_transport_uses_current_api2_and_raw_authorization_token() -> None:
    provider = provider_map()['max_messaging']
    result = build_provider_vendor_transports()['max_messaging'].execute(provider=provider, tenant_id='tenant-a', business_id='business-a', operation='message_send', payload={'chat_id': 99, 'text': 'hello'})
    request = result['request']
    assert request['url_template'] == 'https://platform-api2.max.ru/messages?chat_id=99'
    assert request['headers']['Authorization'] == '{access_token}'
    assert request['json_body'] == {'text': 'hello'}
    assert result['_prepared_only'] is True and result['transport_binding']['live_ready'] is True


def test_vk_max_probe_bindings_are_native_and_live_read_enabled() -> None:
    vk = provider_transport_binding_for_key('vk_messaging')
    max_binding = provider_transport_binding_for_key('max_messaging')
    assert vk['base_url'] == 'https://api.vk.com/method' and vk['probe_path'] == '/groups.getById' and vk['live_ready'] is True
    assert max_binding['base_url'] == 'https://platform-api2.max.ru' and max_binding['probe_path'] == '/me' and max_binding['live_ready'] is True
    transports = build_provider_vendor_transports()
    assert transports['vk_messaging'].execute(provider=provider_map()['vk_messaging'], tenant_id='t', business_id='b', operation='health_probe', payload={})['request']['url_template'].endswith('/groups.getById')
    assert transports['max_messaging'].execute(provider=provider_map()['max_messaging'], tenant_id='t', business_id='b', operation='health_probe', payload={})['request']['url_template'].endswith('/me')


def test_max_official_webhook_secret_header_is_accepted() -> None:
    provider = provider_map()['max_messaging']
    vault = InMemorySecretVault()
    _put(vault, provider, 'webhook_secret', 'max-secret')
    runtime = ProviderWebhookRuntime(vault)
    assert 'X-Max-Bot-Api-Secret' in runtime.describe(provider).header_names
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-Max-Bot-Api-Secret': 'max-secret'}, body=b'{}') is True


def test_vk_max_prepared_transports_remain_bound_when_vault_is_supplied() -> None:
    transports = build_provider_vendor_transports(InMemorySecretVault())
    assert {'vk_messaging', 'max_messaging'} <= set(transports)
    result = transports['vk_messaging'].execute(provider=provider_map()['vk_messaging'], tenant_id='tenant-a', business_id='business-a', operation='health_probe', payload={})
    assert result['_prepared_only'] is True


def test_max_message_read_uses_only_documented_chat_or_message_ids_queries() -> None:
    provider = provider_map()['max_messaging']
    transport = build_provider_vendor_transports()['max_messaging']
    by_chat = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_read', payload={'chat_id': 99})['request']
    by_ids = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_read', payload={'message_ids': 'm1,m2', 'user_id': 7})['request']
    assert by_chat['url_template'] == 'https://platform-api2.max.ru/messages?chat_id=99'
    assert by_ids['url_template'] == 'https://platform-api2.max.ru/messages?message_ids=m1,m2'
