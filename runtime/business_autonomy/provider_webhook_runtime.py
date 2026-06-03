from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from collections.abc import Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderWebhookContract
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_WEBHOOK_RUNTIME = True


@dataclass(frozen=True)
class ProviderWebhookRuntime:
    secret_vault: SecretVault

    def describe(self, provider: ProviderDefinition) -> ProviderWebhookContract:
        if provider.provider_key in {'shopify', 'generic_website', 'wordpress'}:
            return ProviderWebhookContract(
                provider_key=provider.provider_key,
                verification_kind='hmac_sha256_base64',
                header_names=('X-Signature', 'X-Shopify-Hmac-Sha256', 'X-Webhook-Signature'),
                enabled=True,
                metadata={'secret_field': self._secret_field(provider)},
            )
        if provider.provider_key in {'telegram_bot', 'whatsapp_cloud'}:
            return ProviderWebhookContract(
                provider_key=provider.provider_key,
                verification_kind='bearer_or_shared_secret',
                header_names=('Authorization', 'X-Telegram-Bot-Api-Secret-Token', 'X-Hub-Signature-256'),
                enabled=True,
                metadata={'secret_field': self._secret_field(provider)},
            )
        return ProviderWebhookContract(
            provider_key=provider.provider_key,
            verification_kind='none',
            header_names=(),
            enabled=False,
            metadata={},
        )

    def verify(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, headers: Mapping[str, str], body: bytes) -> bool:
        contract = self.describe(provider)
        if not contract.enabled:
            return False
        secret_name = self._secret_field(provider)
        secret = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.{secret_name}')
        if not secret:
            return False
        if contract.verification_kind == 'hmac_sha256_base64':
            expected = base64.b64encode(hmac.new(secret.encode('utf-8'), bytes(body), hashlib.sha256).digest()).decode('ascii')
            candidates = [str(headers.get(name) or '') for name in contract.header_names]
            return any(candidate and hmac.compare_digest(expected, candidate) for candidate in candidates)
        if contract.verification_kind == 'bearer_or_shared_secret':
            bearer = str(headers.get('Authorization') or '')
            candidates = [bearer.removeprefix('Bearer ').strip()] + [str(headers.get(name) or '') for name in contract.header_names if name != 'Authorization']
            return any(candidate and hmac.compare_digest(secret, candidate) for candidate in candidates)
        return False

    def _secret_field(self, provider: ProviderDefinition) -> str:
        for preferred_kind in ('signing_secret', 'token', 'api_key', 'password'):
            for field in provider.secret_fields:
                if field.secret_kind == preferred_kind:
                    return field.secret_name
        return provider.secret_fields[0].secret_name if provider.secret_fields else 'secret'

    def _read_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str:
        ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
        try:
            return self.secret_vault.get(ref).decode('utf-8').strip()
        except Exception:
            return ''


__all__ = ['CANON_PROVIDER_WEBHOOK_RUNTIME', 'ProviderWebhookRuntime']
