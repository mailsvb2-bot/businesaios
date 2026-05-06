from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from security.secret_vault import SecretVault
from urllib.parse import urlencode

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings

CANON_PROVIDER_VENDOR_TRANSPORTS = True


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
        return {'method': 'POST', 'url_template': str(binding['base_url']) + str(binding['sync_path_family']).format(token='{bot_token}', operation=operation), 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class WhatsAppVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'whatsapp_cloud_api'

    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        phone_number_id = str(payload.get('phone_number_id') or '{phone_number_id}')
        path = str(binding['sync_path_family']).format(phone_number_id=phone_number_id, operation=operation)
        return {'method': 'POST', 'url_template': str(binding['base_url']) + path, 'json_body': dict(payload or {})}


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
        query = urlencode({'consumer_key': '{consumer_key}', 'consumer_secret': '{consumer_secret}'})
        return {'method': 'GET' if operation.endswith('_sync') else 'POST', 'url_template': f"{store_url}{path}?{query}", 'json_body': dict(payload or {})}


@dataclass(frozen=True)
class HubSpotVendorTransport(_PreparedOnlyTransport):
    vendor_family: str = 'hubspot_crm_api'

    def _build_request(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        path = str(binding['sync_path_family']).format(operation=operation)
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


def build_provider_vendor_transports(secret_vault: SecretVault | None = None, *, bind_live_network: bool = False) -> dict[str, _PreparedOnlyTransport]:
    if secret_vault is not None:
        from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
        return build_live_http_transports(secret_vault, bind_live_network=bind_live_network)
    return {
        'telegram_bot': TelegramVendorTransport(),
        'whatsapp_cloud': WhatsAppVendorTransport(),
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
