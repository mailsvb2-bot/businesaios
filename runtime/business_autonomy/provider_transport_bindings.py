from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition

CANON_PROVIDER_TRANSPORT_BINDINGS = True

_BINDINGS: Mapping[str, Mapping[str, Any]] = {
    'telegram_bot': {'auth_scheme': 'bearer_token', 'base_url': 'https://api.telegram.org', 'probe_path': '/bot{token}/getMe', 'sync_path_family': '/bot{token}/{operation}', 'live_ready': True},
    'whatsapp_cloud': {'auth_scheme': 'bearer_token', 'base_url': 'https://graph.facebook.com', 'probe_path': '/v19.0/{phone_number_id}', 'sync_path_family': '/v19.0/{phone_number_id}/{operation}', 'live_ready': True},
    'email_connector': {'auth_scheme': 'api_token', 'base_url': 'smtp+https://provider', 'probe_path': '/health', 'sync_path_family': '/mail/{operation}', 'live_ready': False},
    'sms_connector': {'auth_scheme': 'api_token', 'base_url': 'https://sms-gateway.example', 'probe_path': '/health', 'sync_path_family': '/sms/{operation}', 'live_ready': False},
    'generic_website': {'auth_scheme': 'api_key', 'base_url': 'configured-per-business', 'probe_path': '/healthz', 'sync_path_family': '/admin/{operation}', 'live_ready': False},
    'webflow': {'auth_scheme': 'bearer_token', 'base_url': 'https://api.webflow.com', 'probe_path': '/sites', 'sync_path_family': '/{operation}', 'live_ready': True},
    'wordpress': {'auth_scheme': 'basic_or_app_password', 'base_url': 'configured-per-business', 'probe_path': '/wp-json', 'sync_path_family': '/wp-json/wp/v2/{operation}', 'live_ready': False},
    'shopify': {'auth_scheme': 'admin_access_token', 'base_url': 'https://{shop}.myshopify.com', 'probe_path': '/admin/api/2024-10/shop.json', 'sync_path_family': '/admin/api/2024-10/{operation}.json', 'live_ready': True},
    'woocommerce': {'auth_scheme': 'consumer_key_secret', 'base_url': '{store_url}', 'probe_path': '/wp-json/wc/v3', 'sync_path_family': '/wp-json/wc/v3/{operation}', 'live_ready': False},
    'hubspot': {'auth_scheme': 'bearer_token', 'base_url': 'https://api.hubapi.com', 'oauth_base_url': 'https://api.hubapi.com', 'probe_path': '/crm/v3/objects/contacts', 'sync_path_family': '/crm/v3/{operation}', 'live_ready': True},
    'meta_ads': {'auth_scheme': 'bearer_token', 'base_url': 'https://graph.facebook.com', 'probe_path': '/v19.0/me/adaccounts', 'sync_path_family': '/v19.0/{operation}', 'live_ready': True},
    'google_ads': {'auth_scheme': 'oauth_refresh_token', 'base_url': 'https://googleads.googleapis.com', 'oauth_authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth', 'oauth_token_url': 'https://oauth2.googleapis.com/token', 'oauth_scope': 'https://www.googleapis.com/auth/adwords', 'probe_path': '/v16/customers:listAccessibleCustomers', 'sync_path_family': '/v16/{operation}', 'live_ready': False},
    'tiktok_ads': {'auth_scheme': 'bearer_token', 'base_url': 'https://business-api.tiktok.com', 'probe_path': '/open_api/v1.3/oauth2/advertiser/get/', 'sync_path_family': '/open_api/v1.3/{operation}', 'live_ready': False},
    'postgres_runtime': {'auth_scheme': 'dsn', 'base_url': 'postgres://', 'probe_path': 'connection-string', 'sync_path_family': 'sql/{operation}', 'live_ready': True},
    'redis_runtime': {'auth_scheme': 'dsn_or_token', 'base_url': 'redis://', 'probe_path': 'connection-string', 'sync_path_family': 'redis/{operation}', 'live_ready': True},
    'clickhouse_export': {'auth_scheme': 'dsn_or_password', 'base_url': 'https://clickhouse', 'probe_path': '/ping', 'sync_path_family': '/?query={operation}', 'live_ready': True},
}


def provider_transport_binding_for_key(provider_key: str) -> dict[str, Any]:
    key = str(provider_key or '').strip()
    return dict(_BINDINGS.get(key) or {
        'auth_scheme': 'provider_secret_bundle',
        'base_url': 'vendor-configured',
        'probe_path': '/health',
        'sync_path_family': '/{operation}',
        'live_ready': False,
    })


def provider_endpoint_url(provider_key: str, endpoint_key: str = 'base_url', *, default: str = 'vendor-configured') -> str:
    binding = provider_transport_binding_for_key(provider_key)
    value = str(binding.get(str(endpoint_key or 'base_url')) or '').strip()
    return value or str(default)


@dataclass(frozen=True)
class ProviderTransportBindings:
    def describe(self, provider: ProviderDefinition) -> dict[str, Any]:
        base = provider_transport_binding_for_key(provider.provider_key)
        base['provider_key'] = provider.provider_key
        base['connector_id'] = provider.connector_id
        base['webhook_path_family'] = f'/providers/webhook/{{tenant_id}}/{{business_id}}/{provider.provider_key}'
        base['requires_runtime_binding'] = provider.domain == 'platform_infra' or provider.provider_key in {'generic_website', 'wordpress', 'woocommerce'}
        return base


__all__ = [
    'CANON_PROVIDER_TRANSPORT_BINDINGS',
    'ProviderTransportBindings',
    'provider_endpoint_url',
    'provider_transport_binding_for_key',
]
