from __future__ import annotations

from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import ProviderTruthStatus, provider_truth_map
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from security.secret_contract import SecretRef
from security.secret_vault import InMemorySecretVault


def test_slack_and_discord_expose_optional_native_bot_tokens_without_claiming_live_readiness() -> None:
    providers = provider_map()
    for key in ('slack_messaging', 'discord_messaging'):
        fields = {field.secret_name: field for field in providers[key].secret_fields}
        assert fields['webhook_secret'].required is True
        assert fields['bot_token'].required is False
        assert 'message_send' in ProviderSyncRuntimePlanner().describe(providers[key]).write_operations
        assert providers[key].messaging_live_probe_supported is True


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


def test_slack_discord_live_probe_requires_bot_token_without_changing_dry_run() -> None:
    vault = InMemorySecretVault()
    health = ProviderConnectorHealthService(vault)
    for key in ('slack_messaging', 'discord_messaging'):
        provider = provider_map()[key]
        vault.seed_plaintext(
            ref=SecretRef(tenant_id='t', connector_id=provider.connector_id, scope='b', secret_name=f'{provider.connector_id}.webhook_secret'),
            plaintext='bridge-webhook-secret',
        )
        dry = health.probe(provider=provider, tenant_id='t', business_id='b', probe_mode='dry_run')
        live = health.probe(provider=provider, tenant_id='t', business_id='b', probe_mode='live')
        assert dry.status == 'ready_for_credentials'
        assert live.status == 'misconfigured' and live.reason == 'missing_required_secrets'
        assert live.metadata['missing_fields'] == ('bot_token',)


def test_slack_discord_guarded_write_truth_stays_non_live_without_external_proof() -> None:
    truth = provider_truth_map()
    for key in ('slack_messaging', 'discord_messaging'):
        row = truth[key]
        assert row.has_real_endpoint is True
        assert row.has_placeholder_endpoint is False
        assert row.read_only_supported is True
        assert row.write_supported is True
        assert row.status == ProviderTruthStatus.READ_ONLY_READY.value
        assert row.live_ready is False
        assert row.required_credentials == ('webhook_secret',)
        assert row.health_requirements == ('webhook_secret', 'bot_token')


def test_slack_discord_live_transport_enters_control_plane_without_claiming_unconditional_live_write() -> None:
    slack = provider_transport_binding_for_key('slack_messaging')
    discord = provider_transport_binding_for_key('discord_messaging')
    for binding in (slack, discord):
        assert binding['live_probe_ready'] is True
        assert binding['live_read_ready'] is True
        assert binding['live_ready'] is False

    vault = InMemorySecretVault()
    live_transports = build_provider_vendor_transports(vault)
    assert {'slack_messaging', 'discord_messaging'} <= set(live_transports)

    live_runtime = ProviderLiveSyncRuntime(vault, transports=live_transports)
    admin = ProviderAdminService(onboarding_service=None, secret_vault=vault, connector_secret_scope=None, activation_store=None)
    for key in ('slack_messaging', 'discord_messaging'):
        provider = provider_map()[key]
        runner = live_runtime.describe_runner(provider)
        assert runner['transport_bound'] is True
        assert runner['live_run_supported'] is True
        assert runner['live_read_supported'] is True
        assert provider_truth_map()[key].write_supported is True
        assert provider_truth_map()[key].live_ready is False
        live_client = admin.describe_provider_live_client(provider_key=key)
        assert live_client['network_capable'] is True
        assert live_client['transport_type'] == 'VendorHttpLiveTransport'


def test_discord_live_read_rejects_unsafe_channel_path_before_network(monkeypatch) -> None:
    provider = provider_map()['discord_messaging']
    vault = InMemorySecretVault()
    vault.seed_plaintext(
        ref=SecretRef(tenant_id='t', connector_id=provider.connector_id, scope='b', secret_name=f'{provider.connector_id}.bot_token'),
        plaintext='discord-bot-token',
    )
    monkeypatch.setattr(
        'runtime.business_autonomy.provider_http_live_clients._sync_request',
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError('network must stay closed')),
    )
    transport = build_live_http_transports(vault, bind_live_network=True)['discord_messaging']
    result = transport.execute(
        provider=provider, tenant_id='t', business_id='b', operation='message_read',
        payload={'channel_id': '123#', '_allow_network': True},
    )
    assert result['_prepared_only'] is True
    assert result['network_capable'] is False
    assert result['reason'] == 'native_message_read_payload_invalid'
