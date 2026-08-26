from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from application.business_autonomy.provider_runtime_contract import ProviderWebhookContract
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_WEBHOOK_RUNTIME = True
@dataclass(frozen=True)
class ProviderWebhookRuntime:
    secret_vault: SecretVault
    def describe(self, provider: ProviderDefinition) -> ProviderWebhookContract:
        if provider.provider_key in {'shopify', 'generic_website', 'wordpress'}:
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='hmac_sha256_base64', header_names=('X-Signature', 'X-Shopify-Hmac-Sha256', 'X-Webhook-Signature'), enabled=True, metadata={'secret_field': self._secret_field(provider)})
        if provider.provider_key in {'whatsapp_cloud', 'instagram_messaging', 'messenger_messaging'}:
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='hmac_sha256_hex', header_names=('X-Hub-Signature-256',), enabled=True, metadata={'secret_field': 'app_secret', 'challenge_secret_field': 'verify_token', **({'fallback_secret_field': 'webhook_secret'} if provider.provider_key != 'whatsapp_cloud' else {})})
        if provider.provider_key == 'telegram_bot':
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='bearer_or_shared_secret', header_names=('Authorization', 'X-Telegram-Bot-Api-Secret-Token'), enabled=True, metadata={'secret_field': self._secret_field(provider)})
        if describe_provider_messaging_binding(provider) is not None and any(field.secret_kind == 'signing_secret' for field in provider.secret_fields):
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='shared_secret_header', header_names=('Authorization', 'X-BusinessAIOS-Webhook-Secret'), enabled=True, metadata={'secret_field': self._secret_field(provider), 'integration_mode': 'provider_webhook_bridge'})
        return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='none', header_names=(), enabled=False, metadata={})
    def verify(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, headers: Mapping[str, str], body: bytes) -> bool:
        contract = self.describe(provider)
        if not contract.enabled:
            return False
        normalized_headers = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
        secret = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata.get('secret_field') or self._secret_field(provider)}")
        if contract.verification_kind == 'hmac_sha256_hex':
            if secret:
                expected = 'sha256=' + hmac.new(secret.encode('utf-8'), bytes(body), hashlib.sha256).hexdigest()
                return hmac.compare_digest(expected, normalized_headers.get('x-hub-signature-256', ''))
            secret = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata.get('fallback_secret_field')}") if contract.metadata.get('fallback_secret_field') else ''
            bearer = normalized_headers.get('authorization', '')
            return bool(secret) and any(candidate and hmac.compare_digest(secret, candidate) for candidate in (bearer.removeprefix('Bearer ').strip(), normalized_headers.get('x-businessaios-webhook-secret', '')))
        if not secret:
            return False
        if contract.verification_kind == 'hmac_sha256_base64':
            expected = base64.b64encode(hmac.new(secret.encode('utf-8'), bytes(body), hashlib.sha256).digest()).decode('ascii')
            return any(candidate and hmac.compare_digest(expected, candidate) for candidate in (normalized_headers.get(str(name).lower(), '') for name in contract.header_names))
        if contract.verification_kind in {'bearer_or_shared_secret', 'shared_secret_header'}:
            bearer = normalized_headers.get('authorization', '')
            candidates = [bearer.removeprefix('Bearer ').strip()] + [normalized_headers.get(str(name).lower(), '') for name in contract.header_names if str(name).lower() != 'authorization']
            return any(candidate and hmac.compare_digest(secret, candidate) for candidate in candidates)
        return False
    def verify_challenge(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, mode: str, verify_token: str, challenge: str) -> str | None:
        if provider.provider_key not in {'whatsapp_cloud', 'instagram_messaging', 'messenger_messaging'} or str(mode) != 'subscribe':
            return None
        expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.verify_token')
        return str(challenge) if expected and hmac.compare_digest(expected, str(verify_token)) else None
    def _secret_field(self, provider: ProviderDefinition) -> str:
        return next((field.secret_name for preferred_kind in ('signing_secret', 'token', 'api_key', 'password') for field in provider.secret_fields if field.secret_kind == preferred_kind), provider.secret_fields[0].secret_name if provider.secret_fields else 'secret')
    def _read_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str:
        try:
            return self.secret_vault.get(SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)).decode('utf-8').strip()
        except Exception:
            return ''
__all__ = ['CANON_PROVIDER_WEBHOOK_RUNTIME', 'ProviderWebhookRuntime']
