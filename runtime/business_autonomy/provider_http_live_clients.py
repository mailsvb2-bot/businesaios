from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.handler_loader import import_internal_attr
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_HTTP_LIVE_CLIENTS = True


def _sync_request(*args: Any, **kwargs: Any) -> Any:
    return import_internal_attr('runtime._internal.http_transport', 'sync_request')(*args, **kwargs)


@dataclass(frozen=True)
class VendorHttpLiveTransport:
    secret_vault: SecretVault
    provider_key: str
    bind_live_network: bool = False
    timeout_seconds: float = 10.0
    normalizers: ProviderPayloadNormalizers = field(default_factory=ProviderPayloadNormalizers)
    response_parsers: ProviderResponseParsers = field(default_factory=ProviderResponseParsers)

    def execute(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        binding = ProviderTransportBindings().describe(provider)
        normalized_payload = self.normalizers.normalize_outbound(provider=provider, operation=operation, payload=payload)
        prepared = self._prepare_request(provider=provider, tenant_id=tenant_id, business_id=business_id, operation=operation, payload=normalized_payload, binding=binding)
        if not self.bind_live_network or not bool(payload.get('_allow_network', False)):
            return {
                '_prepared_only': True,
                'provider_key': provider.provider_key,
                'network_capable': True,
                'request': prepared,
                'normalized_payload': normalized_payload,
                'transport_binding': binding,
                'response_parser': self.response_parsers.describe(provider=provider),
            }
        body = prepared.get('json_body')
        raw = None if body is None else json.dumps(body, sort_keys=True).encode('utf-8')
        result = _sync_request(
            method=str(prepared.get('method') or 'POST'),
            url=str(prepared['url']),
            headers={str(k): str(v) for k, v in dict(prepared.get('headers') or {}).items()},
            body=raw,
            timeout_s=float(self.timeout_seconds),
        )
        http_status = int(result.status or 599)
        payload_text = str(result.text or '')[:2000]
        parsed = self.response_parsers.parse(
            provider=provider,
            operation=operation,
            response={'http_status': http_status, 'response_body': payload_text, 'error_kind': result.error_kind},
        )
        response: dict[str, Any] = {
            'provider_key': provider.provider_key,
            'network_capable': True,
            'http_status': http_status,
            'response_body': payload_text,
            'request': prepared,
            'parsed_response': parsed,
        }
        if result.error_kind:
            response['error_kind'] = result.error_kind
            response['error_message'] = result.error_message or ''
        return response

    def _prepare_request(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any]) -> Mapping[str, Any]:
        secrets = self._load_secrets(provider=provider, tenant_id=tenant_id, business_id=business_id)
        url = self._render_url(provider=provider, operation=operation, payload=payload, binding=binding, secrets=secrets)
        headers = self._build_headers(provider=provider, secrets=secrets)
        method = 'GET' if operation.endswith('_sync') else 'POST'
        return {'url': url, 'method': method, 'headers': headers, 'json_body': dict(payload or {})}

    def _load_secrets(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str) -> dict[str, str]:
        values = {}
        for field in provider.secret_fields:
            ref = SecretRef(tenant_id=str(tenant_id), connector_id=provider.connector_id, scope=str(business_id), secret_name=f"{provider.connector_id}.{field.secret_name}")
            try:
                values[field.secret_name] = self.secret_vault.get(ref).decode('utf-8')
            except Exception:
                continue
        return values

    def _build_headers(self, *, provider: ProviderDefinition, secrets: Mapping[str, str]) -> Mapping[str, str]:
        if provider.provider_key == 'telegram_bot':
            return {'Content-Type': 'application/json'}
        if provider.provider_key == 'whatsapp_cloud':
            return {'Authorization': f"Bearer {secrets.get('access_token','{access_token}')}", 'Content-Type': 'application/json'}
        if provider.provider_key == 'shopify':
            return {'X-Shopify-Access-Token': secrets.get('admin_access_token', '{admin_access_token}'), 'Content-Type': 'application/json'}
        if provider.provider_key == 'woocommerce':
            return {'Content-Type': 'application/json'}
        if provider.provider_key == 'hubspot':
            return {'Authorization': f"Bearer {secrets.get('private_app_token','{private_app_token}')}", 'Content-Type': 'application/json'}
        if provider.provider_key == 'meta_ads':
            return {'Authorization': f"Bearer {secrets.get('access_token','{access_token}')}", 'Content-Type': 'application/json'}
        if provider.provider_key == 'google_ads':
            return {'Authorization': f"Bearer {secrets.get('access_token','{access_token}')}", 'developer-token': secrets.get('developer_token', '{developer_token}'), 'Content-Type': 'application/json'}
        if provider.provider_key == 'tiktok_ads':
            return {'Access-Token': secrets.get('access_token', '{access_token}'), 'Content-Type': 'application/json'}
        return {'Content-Type': 'application/json'}

    def _render_url(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any], binding: Mapping[str, Any], secrets: Mapping[str, str]) -> str:
        base_url = str(binding.get('base_url') or '')
        path_family = str(binding.get('sync_path_family') or '')
        if provider.provider_key == 'telegram_bot':
            return f"{base_url}{path_family.format(token=secrets.get('bot_token','{bot_token}'), operation=operation)}"
        if provider.provider_key == 'whatsapp_cloud':
            return f"{base_url}{path_family.format(phone_number_id=secrets.get('phone_number_id', payload.get('phone_number_id','{phone_number_id}')), operation=operation)}"
        if provider.provider_key == 'shopify':
            shop = str(payload.get('shop') or secrets.get('shop') or '{shop}')
            return f"{base_url.format(shop=shop)}{path_family.format(operation=operation)}"
        if provider.provider_key == 'woocommerce':
            store_url = str(secrets.get('store_url') or payload.get('store_url') or '{store_url}')
            return f"{store_url}{path_family.format(operation=operation)}"
        if provider.provider_key == 'hubspot':
            return f"{base_url}{path_family.format(operation=operation)}"
        if provider.provider_key == 'meta_ads':
            account_id = str(secrets.get('account_id') or payload.get('account_id') or '{account_id}')
            return f"{base_url}{path_family.format(operation=operation).replace('{account_id}', account_id)}"
        if provider.provider_key == 'google_ads':
            customer_id = str(secrets.get('customer_id') or payload.get('customer_id') or '{customer_id}')
            return f"{base_url}{path_family.format(operation=operation).replace('{customer_id}', customer_id)}"
        if provider.provider_key == 'tiktok_ads':
            return f"{base_url}{path_family.format(operation=operation)}"
        return f"{base_url}{path_family.format(operation=operation)}"


def build_live_http_transports(secret_vault: SecretVault, *, bind_live_network: bool = False) -> dict[str, VendorHttpLiveTransport]:
    providers = ('telegram_bot','whatsapp_cloud','shopify','woocommerce','hubspot','meta_ads','google_ads','tiktok_ads')
    return {key: VendorHttpLiveTransport(secret_vault=secret_vault, provider_key=key, bind_live_network=bind_live_network) for key in providers}


__all__ = ['CANON_PROVIDER_HTTP_LIVE_CLIENTS', 'VendorHttpLiveTransport', 'build_live_http_transports']
