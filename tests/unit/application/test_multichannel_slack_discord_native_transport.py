from __future__ import annotations

from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from security.secret_vault import InMemorySecretVault


def test_slack_and_discord_expose_optional_native_bot_tokens_without_claiming_live_readiness() -> None:
    providers = provider_map()
    for key in ('slack_messaging', 'discord_messaging'):
        fields = {field.secret_name: field for field in providers[key].secret_fields}
        assert fields['webhook_secret'].required is True
        assert fields['bot_token'].required is False
        assert 'message_send' in ProviderSyncRuntimePlanner().describe(providers[key]).write_operations
        assert providers[key].messaging_live_probe_supported is False


def test_slack_prepared_native_transport_matches_web_api_contract() -> None:
    provider = provider_map()['slack_messaging']
    transport = build_provider_vendor_transports()['slack_messaging']
    probe = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='health_probe', payload={})['request']
    read = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_read', payload={'channel_id': 'C123'})['request']
    send = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_send', payload={'channel_id': 'C123', 'message': 'hello'})['request']
    assert probe == {'method': 'POST', 'url_template': 'https://slack.com/api/auth.test', 'headers': {'Authorization': 'Bearer {bot_token}'}, 'json_body': None}
    assert read == {'method': 'GET', 'url_template': 'https://slack.com/api/conversations.history?channel=C123', 'headers': {'Authorization': 'Bearer {bot_token}'}, 'json_body': None}
    assert send == {'method': 'POST', 'url_template': 'https://slack.com/api/chat.postMessage', 'headers': {'Authorization': 'Bearer {bot_token}'}, 'json_body': {'channel': 'C123', 'text': 'hello'}}


def test_discord_prepared_native_transport_matches_v10_bot_contract() -> None:
    provider = provider_map()['discord_messaging']
    transport = build_provider_vendor_transports()['discord_messaging']
    probe = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='health_probe', payload={})['request']
    read = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_read', payload={'channel_id': '123'})['request']
    send = transport.execute(provider=provider, tenant_id='t', business_id='b', operation='message_send', payload={'channel_id': '123', 'text': 'hello'})['request']
    assert probe == {'method': 'GET', 'url_template': 'https://discord.com/api/v10/users/@me', 'headers': {'Authorization': 'Bot {bot_token}'}, 'json_body': None}
    assert read == {'method': 'GET', 'url_template': 'https://discord.com/api/v10/channels/123/messages', 'headers': {'Authorization': 'Bot {bot_token}'}, 'json_body': None}
    assert send == {'method': 'POST', 'url_template': 'https://discord.com/api/v10/channels/123/messages', 'headers': {'Authorization': 'Bot {bot_token}'}, 'json_body': {'content': 'hello', 'allowed_mentions': {'parse': []}}}


def test_slack_discord_prepared_transports_stay_out_of_live_control_plane() -> None:
    slack = provider_transport_binding_for_key('slack_messaging')
    discord = provider_transport_binding_for_key('discord_messaging')
    assert slack['base_url'] == 'https://slack.com/api' and slack['probe_path'] == '/auth.test' and slack['live_ready'] is False
    assert discord['base_url'] == 'https://discord.com/api/v10' and discord['probe_path'] == '/users/@me' and discord['live_ready'] is False

    vault = InMemorySecretVault()
    live_transports = build_provider_vendor_transports(vault)
    assert {'slack_messaging', 'discord_messaging'}.isdisjoint(live_transports)

    prepared_transports = build_provider_vendor_transports()
    live_runtime = ProviderLiveSyncRuntime(vault, transports=live_transports)
    admin = ProviderAdminService(
        onboarding_service=None,
        secret_vault=vault,
        connector_secret_scope=None,
        activation_store=None,
    )
    for key in ('slack_messaging', 'discord_messaging'):
        provider = provider_map()[key]
        prepared = prepared_transports[key].execute(
            provider=provider,
            tenant_id='t',
            business_id='b',
            operation='health_probe',
            payload={},
        )
        assert prepared['_prepared_only'] is True
        assert prepared['transport_binding']['live_ready'] is False

        runner = live_runtime.describe_runner(provider)
        assert runner['transport_bound'] is False
        assert runner['live_run_supported'] is False

        live_client = admin.describe_provider_live_client(provider_key=key)
        assert live_client['network_capable'] is False
        assert live_client['transport_type'] is None
