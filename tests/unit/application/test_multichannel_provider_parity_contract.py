from __future__ import annotations

import json

import pytest

from application.business_autonomy.non_ai_onboarding_mode import NonAiOperatingMode
from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_CHANNEL_PROVIDER_KEYS,
    MESSAGING_INTERNAL_CHANNELS,
    provider_map,
)
from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_webhook_messaging_bridge import resolve_provider_webhook_messaging_ingress
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.messaging import CHANNEL_SPECS
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault

SAMPLES = {
    'telegram': {'message': {'from': {'id': 1}, 'chat': {'id': 1}, 'text': 'tg', 'message_id': 11}, 'update_id': 101},
    'whatsapp': {'entry': [{'changes': [{'value': {'messages': [{'from': 'wa1', 'id': 'wamid', 'text': {'body': 'wa'}}]}}]}]},
    'vk': {'object': {'message': {'from_id': 2, 'peer_id': 2, 'text': 'vk', 'id': 22}}, 'event_id': 'vk-event'},
    'max': {'message': {'sender': {'user_id': 3}, 'recipient': {'chat_id': 3}, 'body': {'text': 'max', 'mid': 'max-mid'}}},
    'instagram': {'entry': [{'messaging': [{'sender': {'id': 'ig1'}, 'message': {'text': 'ig', 'mid': 'ig-mid'}}]}]},
    'messenger': {'entry': [{'messaging': [{'sender': {'id': 'fb1'}, 'message': {'text': 'fb', 'mid': 'fb-mid'}}]}]},
    'slack': {'event': {'user': 'U1', 'channel': 'C1', 'text': 'slack', 'client_msg_id': 'slack-mid'}},
    'discord': {'author': {'id': 'd1'}, 'channel_id': 'dc1', 'content': 'discord', 'id': 'discord-mid'},
    'viber': {'sender': {'id': 'v1'}, 'message': {'text': 'viber'}, 'message_token': 'v-mid'},
    'line': {'events': [{'source': {'userId': 'l1'}, 'message': {'text': 'line', 'id': 'l-mid'}, 'timestamp': 1}]},
    'wechat': {'FromUserName': 'w1', 'ToUserName': 'biz', 'Content': 'wechat', 'MsgId': 'w-mid'},
    'kakaotalk': {'userRequest': {'user': {'id': 'k1'}, 'utterance': 'kakao', 'block': {'id': 'k-mid'}}},
    'sms': {'from': '+100', 'to': '+200', 'body': 'sms', 'message_id': 'sms-mid'},
    'email': {'from': 'a@example.com', 'to': 'b@example.com', 'text': 'email', 'message_id': 'mail-mid'},
    'web_chat': {'user_id': 'web1', 'text': 'web', 'message_id': 'web-mid'},
}


def test_every_external_canonical_messaging_channel_has_provider_control_plane_surface() -> None:
    assert set(CHANNEL_SPECS) == set(MESSAGING_CHANNEL_PROVIDER_KEYS) | set(MESSAGING_INTERNAL_CHANNELS)


def test_every_external_messaging_provider_uses_a_canonical_non_ai_mode() -> None:
    valid = {mode.value for mode in NonAiOperatingMode}
    providers = provider_map()
    assert all(providers[key].default_non_ai_mode in valid for key in MESSAGING_CHANNEL_PROVIDER_KEYS.values())
    providers = provider_map()
    for channel, provider_key in MESSAGING_CHANNEL_PROVIDER_KEYS.items():
        assert provider_key in providers
        assert providers[provider_key].messaging_channel == channel


@pytest.mark.parametrize('channel', sorted(SAMPLES))
def test_provider_webhook_bridge_uses_canonical_decoder_for_every_mapped_channel(channel: str) -> None:
    provider = provider_map()[MESSAGING_CHANNEL_PROVIDER_KEYS[channel]]
    ingress = resolve_provider_webhook_messaging_ingress(provider=provider, normalized_payload=SAMPLES[channel])
    assert ingress is not None
    assert ingress.channel == channel
    assert ingress.user_id
    assert ingress.text
    assert ingress.transport_message_id


def test_bridge_providers_are_signed_read_capable_and_write_planned_but_not_publicly_enabled() -> None:
    providers = provider_map()
    marketplace = {row['provider_key']: row for row in public_integration_marketplace()}
    for provider_key in BRIDGE_MESSAGING_PROVIDER_KEYS:
        provider = providers[provider_key]
        plan = ProviderSyncRuntimePlanner().describe(provider)
        contract = ProviderWebhookRuntime(InMemorySecretVault()).describe(provider)
        assert plan.read_operations == ('message_read',)
        assert plan.write_operations == ('message_send',)
        assert contract.enabled is True
        expected_verifier = (
            'hmac_sha256_hex'
            if provider_key in {'instagram_messaging', 'messenger_messaging'}
            else 'shared_secret_body_or_header'
            if provider_key == 'vk_messaging'
            else 'slack_hmac_sha256_v0_or_shared_secret'
            if provider_key == 'slack_messaging'
            else 'shared_secret_header'
        )
        assert contract.verification_kind == expected_verifier
        assert marketplace[provider_key]['selectable'] is True
        assert marketplace[provider_key]['read_supported'] is True
        assert marketplace[provider_key]['write_supported'] is False
        assert marketplace[provider_key]['connection_mode'] == 'provider_webhook_bridge'


def test_marketplace_exposes_channel_specific_connection_modes() -> None:
    marketplace = {row['provider_key']: row for row in public_integration_marketplace()}
    assert marketplace['telegram_bot']['connection_mode'] == 'provider_native_api'
    assert marketplace['whatsapp_cloud']['connection_mode'] == 'provider_webhook_and_cloud_api'
    assert marketplace['email_connector']['connection_mode'] == 'mailbox_or_provider_api'
    assert marketplace['sms_connector']['connection_mode'] == 'sms_gateway'
    assert marketplace['generic_website']['connection_mode'] == 'web_ingress'


def test_onboarding_can_select_every_external_messaging_channel(tmp_path) -> None:
    provider_keys = tuple(MESSAGING_CHANNEL_PROVIDER_KEYS.values())
    result = CTALandingIntakeService(storage_path=str(tmp_path / 'intakes.jsonl')).submit(payload={'business_name': 'Omnichannel', 'email': 'owner@example.com', 'selected_providers': list(provider_keys)})
    assert len(provider_keys) == 15
    assert result.selected_providers == provider_keys
    assert len(result.integration_plan) == len(provider_keys)


def test_bridge_shared_secret_is_verified_fail_closed() -> None:
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.webhook_secret')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=b'shared-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = json.dumps(SAMPLES['vk']).encode()
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'shared-secret'}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'X-BusinessAIOS-Webhook-Secret': 'wrong'}, body=body) is False
