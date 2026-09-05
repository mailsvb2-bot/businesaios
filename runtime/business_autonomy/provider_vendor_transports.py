from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from security.secret_vault import SecretVault

CANON_PROVIDER_VENDOR_TRANSPORTS = True


def _query_string(params: Mapping[str, str]) -> str:
    # Prepared-only templates here use controlled placeholder tokens. Keep this
    # local and deterministic so runtime/business does not import raw URL SDKs.
    parts = []
    for key, value in params.items():
        k = str(key).strip()
        v = str(value).strip()
        if not k:
            continue
        if any(ch.isspace() for ch in k):
            raise ValueError('query parameter keys must not contain whitespace')
        parts.append(f'{k}={v}')
    return '&'.join(parts)


@dataclass(frozen=True)
class _PreparedOnlyTransport:
    vendor_family: str
    normalizers: ProviderPayloadNormalizers = field(default_factory=ProviderPayloadNormalizers)
    def execute(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        binding = ProviderTransportBindings().describe(provider)
        normalized_payload = self.normalizers.normalize_outbound(provider=provider, operation=operation, payload=payload)
        request = self._build_request(provider=provider, operation=operation, payload=normalized_payload, binding=binding)
        return {
            '_prepared_only': True,
            'vendor_family': self.vendor_family,
            'provider_key': provider.provider_key,
            'request': request,
            'transport_binding': binding,
            'tenant_id': str(tenant_id),
            'business_id': str(business_id),
            'normalized_payload': normalized_payload,
        }
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

@dataclass(frozen=True)
class TelegramVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'telegram_bot_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return {'method': 'GET' if operation in {'message_read', 'contact_profile_read'} else 'POST', 'url_template': str(binding['base_url']) + '/bot{bot_token}/' + {'message_read': 'getUpdates', 'contact_profile_read': 'getMe'}.get(operation, operation), 'json_body': dict(payload or {})}

@dataclass(frozen=True)
class WhatsAppVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'whatsapp_cloud_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        phone_number_id = str(payload.get('phone_number_id') or '{phone_number_id}')
        path = str(binding['sync_path_family']).format(phone_number_id=phone_number_id, operation=operation)
        return {'method': 'POST', 'url_template': str(binding['base_url']) + path, 'json_body': dict(payload or {})}

@dataclass(frozen=True)
class NativeMessagingVendorTransport(_PreparedOnlyTransport):
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        if provider.provider_key in {'instagram_messaging', 'messenger_messaging'}:
            if operation != 'message_send':
                raise ValueError('Meta messaging native reads are webhook-driven')
            return {'method': 'POST', 'url_template': str(binding['base_url']) + str(binding['sync_path_family']).format(**({'ig_user_id': '{ig_user_id}'} if provider.provider_key == 'instagram_messaging' else {'page_id': '{page_id}'})), 'headers': {'Authorization': 'Bearer {access_token}'}, 'json_body': {'recipient': {'id': str(payload.get('recipient_id') or '{recipient_id}')}, **({'messaging_type': 'RESPONSE'} if provider.provider_key == 'messenger_messaging' else {}), 'message': {'text': str(payload.get('text') or '')}}}
        if provider.provider_key == 'line_messaging':
            if operation == 'message_read':
                raise ValueError('LINE message reads are webhook-driven')
            return {'method': 'GET' if operation == 'health_probe' else 'POST', 'url_template': str(binding['base_url']) + ('/v2/bot/info' if operation == 'health_probe' else '/v2/bot/message/push'), 'headers': {'Authorization': 'Bearer {channel_access_token}'}, 'json_body': None if operation == 'health_probe' else dict(payload or {})}
        if provider.provider_key == 'viber_messaging':
            if operation == 'message_read':
                raise ValueError('Viber message reads are webhook-driven')
            return {'method': 'POST', 'url_template': str(binding['base_url']) + ('/get_account_info' if operation == 'health_probe' else '/send_message'), 'headers': {'X-Viber-Auth-Token': '{auth_token}'}, 'json_body': {} if operation == 'health_probe' else dict(payload or {})}
        if provider.provider_key == 'max_messaging':
            recipient = (('chat_id', payload.get('chat_id')) if payload.get('chat_id') else ('message_ids', payload.get('message_ids') or '{message_ids}')) if operation == 'message_read' else (('chat_id', payload.get('chat_id')) if payload.get('chat_id') else ('user_id', payload.get('user_id') or '{user_id}'))
            return {'method': 'GET' if operation in {'health_probe', 'message_read'} else 'POST', 'url_template': str(binding['base_url']) + ({'health_probe': '/me', 'message_read': '/messages'}.get(operation, '/messages')) + ('' if operation == 'health_probe' else f'?{recipient[0]}={recipient[1]}'), 'headers': {'Authorization': '{access_token}'}, 'json_body': None if operation in {'health_probe', 'message_read'} else {'text': payload.get('text', '')}}
        if provider.provider_key == 'slack_messaging':
            channel = str(payload.get('channel') or payload.get('channel_id') or '{channel_id}')
            return {'method': 'POST' if operation != 'message_read' else 'GET', 'url_template': str(binding['base_url']) + ({'health_probe': '/auth.test', 'message_read': '/conversations.history'}.get(operation, '/chat.postMessage')) + (('?' + _query_string({'channel': channel})) if operation == 'message_read' else ''), 'headers': {'Authorization': 'Bearer {bot_token}'}, 'json_body': {'channel': channel, 'text': str(payload.get('text') or '')} if operation not in {'health_probe', 'message_read'} else None}
        if provider.provider_key == 'discord_messaging':
            channel = str(payload.get('channel_id') or '{channel_id}')
            return {'method': 'GET' if operation in {'health_probe', 'message_read'} else 'POST', 'url_template': str(binding['base_url']) + ('/users/@me' if operation == 'health_probe' else f'/channels/{channel}/messages'), 'headers': {'Authorization': 'Bot {bot_token}'}, 'json_body': None if operation in {'health_probe', 'message_read'} else {'content': str(payload.get('text') or ''), 'allowed_mentions': {'parse': []}}}
        endpoint = {'health_probe': 'groups.getById', 'message_read': 'messages.getConversations'}.get(operation, 'messages.send')
        return {'method': 'POST', 'url_template': str(binding['base_url']) + '/' + endpoint, 'form_body': {**dict(payload or {}), 'access_token': '{access_token}', 'v': '5.199'}}

@dataclass(frozen=True)
class ShopifyVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'shopify_admin_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        shop = str(payload.get('shop') or '{shop}')
        path = str(binding['sync_path_family']).format(operation=operation)
        return {'method': 'GET' if operation.endswith('_sync') else 'POST', 'url_template': str(binding['base_url']).format(shop=shop) + path, 'headers': {'X-Shopify-Access-Token': '{admin_access_token}'}, 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class WooCommerceVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'woocommerce_rest_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        store_url = str(payload.get('store_url') or '{store_url}')
        path = str(binding['sync_path_family']).format(operation=operation)
        query = _query_string({'consumer_key': '{consumer_key}', 'consumer_secret': '{consumer_secret}'})
        return {'method': 'GET' if operation.endswith('_sync') else 'POST', 'url_template': f"{store_url}{path}?{query}", 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class HubSpotVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'hubspot_crm_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        path = '/crm/objects/2026-03/' + {'contact_sync': 'contacts', 'deal_sync': 'deals'}.get(operation, operation)
        return {'method': 'GET' if operation.endswith('_sync') else 'POST', 'url_template': str(binding['base_url']) + path, 'headers': {'Authorization': 'Bearer {private_app_token}'}, 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class MetaAdsVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'meta_graph_ads_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        account_id = str(payload.get('account_id') or '{account_id}')
        return {'method': 'POST' if 'launch' in operation or 'update' in operation or 'pause' in operation else 'GET', 'url_template': str(binding['base_url']) + str(binding['sync_path_family']).format(operation=operation).replace('{account_id}', account_id), 'headers': {'Authorization': 'Bearer {access_token}'}, 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class GoogleAdsVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'google_ads_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        customer_id = str(payload.get('customer_id') or '{customer_id}')
        path = str(binding['sync_path_family']).format(operation=operation).replace('{customer_id}', customer_id)
        return {'method': 'POST', 'url_template': str(binding['base_url']) + path, 'headers': {'Authorization': 'Bearer {access_token}', 'developer-token': '{developer_token}'}, 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class TikTokAdsVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'tiktok_ads_api'
    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return {'method': 'POST' if 'launch' in operation or 'update' in operation or 'pause' in operation else 'GET', 'url_template': str(binding['base_url']) + str(binding['sync_path_family']).format(operation=operation), 'headers': {'Access-Token': '{access_token}'}, 'json_body': dict(payload or {})}


def build_provider_vendor_transports(secret_vault: SecretVault | None = None, *, bind_live_network: bool = True, media_preparation: Any | None = None) -> dict[str, _PreparedOnlyTransport]:
    if secret_vault is not None:
        from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
        from runtime.business_autonomy.provider_smtp_live_client import ProviderSmtpLiveTransport
        transports = build_live_http_transports(secret_vault, bind_live_network=bind_live_network, media_preparation=media_preparation)
        transports['email_connector'] = ProviderSmtpLiveTransport(secret_vault=secret_vault, bind_live_network=bind_live_network)
        return transports
    return {
        'telegram_bot': TelegramVendorTransport(),
        'whatsapp_cloud': WhatsAppVendorTransport(),
        **{key: NativeMessagingVendorTransport(vendor_family='native_messaging_api') for key in ('vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging', 'instagram_messaging', 'messenger_messaging', 'line_messaging', 'viber_messaging')},
        'shopify': ShopifyVendorTransport(),
        'woocommerce': WooCommerceVendorTransport(),
        'hubspot': HubSpotVendorTransport(),
        'meta_ads': MetaAdsVendorTransport(),
        'google_ads': GoogleAdsVendorTransport(),
        'tiktok_ads': TikTokAdsVendorTransport(),
    }


__all__ = [
    'CANON_PROVIDER_VENDOR_TRANSPORTS',
    'TelegramVendorTransport',
    'WhatsAppVendorTransport',
    'ShopifyVendorTransport',
    'WooCommerceVendorTransport',
    'HubSpotVendorTransport',
    'MetaAdsVendorTransport',
    'GoogleAdsVendorTransport',
    'TikTokAdsVendorTransport',
    'build_provider_vendor_transports',
]
