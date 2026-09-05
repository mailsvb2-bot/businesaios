from __future__ import annotations

from dataclasses import dataclass

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderHealthProbeResult
from contracts.email_outbound import (
    normalize_email_address,
    normalize_smtp_host,
    normalize_smtp_port,
    normalize_smtp_security,
)
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_CONNECTOR_HEALTH = True
_REQUIRED_BY_PROVIDER = {
    'telegram_bot': ('bot_token',),
    'whatsapp_cloud': ('access_token', 'phone_number_id'),
    'email_connector': ('smtp_host', 'smtp_port', 'smtp_security', 'from_address'),
    'sms_connector': ('api_token', 'sender_id'),
    'generic_website': ('webhook_secret',),
    'webflow': ('api_token',),
    'wordpress': ('application_password',),
    'shopify': ('admin_access_token', 'webhook_secret'),
    'woocommerce': ('consumer_key', 'consumer_secret', 'store_url'),
    'amazon_marketplace': ('refresh_token', 'seller_id'),
    'ebay_marketplace': ('oauth_token', 'marketplace_id'),
    'etsy_marketplace': ('api_key', 'shop_id'),
    'wildberries_marketplace': ('api_token',),
    'ozon_marketplace': ('client_id', 'api_key'),
    'hubspot': ('private_app_token',),
    'meta_ads': ('access_token', 'account_id'),
    'google_ads': ('developer_token', 'refresh_token', 'client_id', 'client_secret'),
    'tiktok_ads': ('access_token', 'advertiser_id'),
    'postgres_runtime': ('dsn',),
    'redis_runtime': ('redis_url',),
    'clickhouse_export': ('endpoint', 'database'),
}


def _has_http_endpoint_shape(value: str) -> bool:
    text = str(value or '').strip()
    if not text:
        return False
    lower = text.lower()
    if lower.startswith('https://'):
        rest = text[8:]
    elif lower.startswith('http://'):
        rest = text[7:]
    else:
        return False
    host = rest.split('/', 1)[0].split('?', 1)[0].split('#', 1)[0].strip()
    return bool(host and not host.startswith(':') and ' ' not in host)


@dataclass(frozen=True)
class ProviderConnectorHealthService:
    secret_vault: SecretVault

    def probe(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, probe_mode: str = 'dry_run') -> ProviderHealthProbeResult:
        mode = str(probe_mode or 'dry_run').strip().lower() or 'dry_run'
        binding, present, missing = provider_transport_binding_for_key(provider.provider_key), [], []
        required = (*_REQUIRED_BY_PROVIDER.get(provider.provider_key, tuple(field.field_key for field in provider.secret_fields if field.required)), *(binding.get('live_required_secrets', ()) if mode == 'live' else ()))
        for field_key in required:
            value = self._read_optional_secret(
                tenant_id=tenant_id,
                connector_id=provider.connector_id,
                business_id=business_id,
                secret_name=f'{provider.connector_id}.{field_key}',
            )
            if value:
                present.append(field_key)
            else:
                missing.append(field_key)
        if missing:
            return ProviderHealthProbeResult(
                provider_key=provider.provider_key, status='misconfigured',
                probe_mode=mode, reason='missing_required_secrets',
                metadata={'missing_fields': tuple(missing), 'present_fields': tuple(present)},
            )
        shallow = self._shallow_validate(provider_key=provider.provider_key, tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id)
        if not shallow[0]:
            return ProviderHealthProbeResult(
                provider_key=provider.provider_key, status='invalid_secret_shape',
                probe_mode=mode, reason=shallow[1],
                metadata={'present_fields': tuple(present)},
            )
        live_probe_ready = bool(binding.get('live_probe_ready', binding.get('live_ready')))
        if mode == 'live' and not live_probe_ready:
            return ProviderHealthProbeResult(
                provider_key=provider.provider_key, status='live_probe_unsupported',
                probe_mode=mode, reason='live_transport_not_ready',
                metadata={'present_fields': tuple(present), 'live_probe_supported': False},
            )
        return ProviderHealthProbeResult(
            provider_key=provider.provider_key, status='ready_for_live_probe' if mode == 'live' else 'ready_for_credentials',
            probe_mode=mode, reason='validated_secret_shape',
            metadata={'present_fields': tuple(present), 'live_probe_supported': live_probe_ready},
        )

    def _shallow_validate(self, *, provider_key: str, tenant_id: str, connector_id: str, business_id: str) -> tuple[bool, str]:
        if provider_key == 'email_connector':
            try:
                normalize_smtp_host(self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.smtp_host'))
                normalize_smtp_port(self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.smtp_port'))
                normalize_smtp_security(self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.smtp_security'))
                normalize_email_address(self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.from_address'))
            except ValueError:
                return False, 'invalid_smtp_configuration'
            username = self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.smtp_username')
            password = self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.smtp_password') or self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.api_token')
            if bool(username) != bool(password):
                return False, 'incomplete_smtp_authentication'
            return True, 'ok'
        if provider_key == 'postgres_runtime':
            dsn = self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.dsn')
            return (dsn.startswith('postgres://') or dsn.startswith('postgresql://'), 'invalid_postgres_dsn' if dsn else 'missing_postgres_dsn')
        if provider_key == 'redis_runtime':
            url = self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.redis_url')
            return (url.startswith('redis://') or url.startswith('rediss://'), 'invalid_redis_url' if url else 'missing_redis_url')
        if provider_key == 'clickhouse_export':
            endpoint = self._read_optional_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=f'{connector_id}.endpoint')
            return (_has_http_endpoint_shape(endpoint), 'invalid_clickhouse_endpoint' if endpoint else 'missing_clickhouse_endpoint')
        return True, 'ok'

    def _read_optional_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str:
        ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
        try:
            return self.secret_vault.get(ref).decode('utf-8').strip()
        except Exception:
            return ''


__all__ = ['CANON_PROVIDER_CONNECTOR_HEALTH', 'ProviderConnectorHealthService']
