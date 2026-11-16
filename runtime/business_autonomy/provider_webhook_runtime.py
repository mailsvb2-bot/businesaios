from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from application.business_autonomy.provider_runtime_contract import ProviderWebhookContract
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_WEBHOOK_RUNTIME = True
RAW_SIGNATURE_FIRST_PROVIDER_KEYS = frozenset({'line_messaging', 'viber_messaging', 'telegram_bot'})

def _secret_eq(expected: object, observed: object) -> bool:
    """Compare untrusted webhook secrets without non-ASCII compare_digest errors."""
    return bool(expected) and hmac.compare_digest(
        str(expected).encode("utf-8"), str(observed or "").encode("utf-8")
    )


@dataclass(frozen=True)
class ProviderWebhookRuntime:
    secret_vault: SecretVault

    def describe(self, provider: ProviderDefinition) -> ProviderWebhookContract:
        if provider.provider_key in {'shopify', 'generic_website', 'wordpress'}:
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='hmac_sha256_base64', header_names=('X-Signature', 'X-Shopify-Hmac-Sha256', 'X-Webhook-Signature'), enabled=True, metadata={'secret_field': self._secret_field(provider)})
        if provider.provider_key in {'whatsapp_cloud', 'instagram_messaging', 'messenger_messaging'}:
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='hmac_sha256_hex', header_names=('X-Hub-Signature-256',), enabled=True, metadata={'secret_field': 'app_secret', 'challenge_secret_field': 'verify_token', **({'fallback_secret_field': 'webhook_secret'} if provider.provider_key != 'whatsapp_cloud' else {})})
        if provider.provider_key == 'slack_messaging':
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='slack_hmac_sha256_v0_or_shared_secret', header_names=('X-Slack-Signature', 'X-Slack-Request-Timestamp', 'Authorization', 'X-BusinessAIOS-Webhook-Secret'), enabled=True, metadata={'secret_field': 'webhook_secret', 'integration_mode': 'native_slack_events_or_provider_webhook_bridge', 'max_request_age_seconds': 300})
        if provider.provider_key == 'discord_messaging':
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='discord_ed25519_or_shared_secret', header_names=('X-Signature-Ed25519', 'X-Signature-Timestamp', 'Authorization', 'X-BusinessAIOS-Webhook-Secret'), enabled=True, metadata={'secret_field': 'webhook_secret', 'native_public_key_field': 'application_public_key', 'integration_mode': 'native_discord_http_or_provider_webhook_bridge'})
        if provider.provider_key in {'line_messaging', 'viber_messaging'}:
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='line_hmac_sha256_base64_or_shared_secret' if provider.provider_key == 'line_messaging' else 'viber_hmac_sha256_hex_or_shared_secret', header_names=(('X-Line-Signature' if provider.provider_key == 'line_messaging' else 'X-Viber-Content-Signature'), 'Authorization', 'X-BusinessAIOS-Webhook-Secret'), enabled=True, metadata={'secret_field': 'webhook_secret', 'native_secret_field': 'channel_secret' if provider.provider_key == 'line_messaging' else 'auth_token', 'integration_mode': 'native_line_messaging_api_or_provider_webhook_bridge' if provider.provider_key == 'line_messaging' else 'native_viber_bot_api_or_provider_webhook_bridge'})
        if provider.provider_key == 'telegram_bot':
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='bearer_or_shared_secret', header_names=('Authorization', 'X-Telegram-Bot-Api-Secret-Token'), enabled=True, metadata={'secret_field': self._secret_field(provider)})
        if describe_provider_messaging_binding(provider) is not None and any(field.secret_kind == 'signing_secret' for field in provider.secret_fields):
            return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='shared_secret_body_or_header' if provider.provider_key == 'vk_messaging' else 'shared_secret_header', header_names=('Authorization', 'X-BusinessAIOS-Webhook-Secret', *(('X-Max-Bot-Api-Secret',) if provider.provider_key == 'max_messaging' else ())), enabled=True, metadata={'secret_field': self._secret_field(provider), 'integration_mode': 'provider_webhook_bridge'})
        return ProviderWebhookContract(provider_key=provider.provider_key, verification_kind='none', header_names=(), enabled=False, metadata={})

    def verify(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, headers: Mapping[str, str], body: bytes) -> bool:
        contract = self.describe(provider)
        if not contract.enabled:
            return False
        normalized_headers = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
        secret = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata.get('secret_field') or self._secret_field(provider)}")
        if contract.verification_kind == 'hmac_sha256_hex':
            if secret is not None:
                signature_valid = bool(secret) and _secret_eq('sha256=' + hmac.new(secret.encode('utf-8'), bytes(body), hashlib.sha256).hexdigest(), normalized_headers.get('x-hub-signature-256', ''))
            else:
                secret = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata.get('fallback_secret_field')}") if contract.metadata.get('fallback_secret_field') else ''
                signature_valid = bool(secret) and any(candidate and _secret_eq(secret, candidate) for candidate in (normalized_headers.get('authorization', '').removeprefix('Bearer ').strip(), normalized_headers.get('x-businessaios-webhook-secret', '')))
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        if contract.verification_kind == 'discord_ed25519_or_shared_secret':
            signature, timestamp = normalized_headers.get('x-signature-ed25519', '').strip(), normalized_headers.get('x-signature-timestamp', '').strip()
            if signature or timestamp:
                public_key = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata['native_public_key_field']}")
                if not signature or not timestamp or not public_key or len(signature) != 128 or len(public_key) != 64:
                    return False
                try:
                    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(bytes.fromhex(signature), timestamp.encode('utf-8') + bytes(body))
                except (InvalidSignature, ValueError):
                    return False
                return self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
            signature_valid = bool(secret) and any(candidate and _secret_eq(secret, candidate) for candidate in (normalized_headers.get('authorization', '').removeprefix('Bearer ').strip(), normalized_headers.get('x-businessaios-webhook-secret', '')))
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        if contract.verification_kind in {'line_hmac_sha256_base64_or_shared_secret', 'viber_hmac_sha256_hex_or_shared_secret'}:
            header_name = 'x-line-signature' if provider.provider_key == 'line_messaging' else 'x-viber-content-signature'
            if header_name in normalized_headers:
                signature, native_secret = normalized_headers.get(header_name, '').strip(), self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.{contract.metadata['native_secret_field']}")
                if not signature or not native_secret:
                    return False
                expected = base64.b64encode(hmac.new(native_secret.encode('utf-8'), bytes(body), hashlib.sha256).digest()).decode('ascii') if provider.provider_key == 'line_messaging' else hmac.new(native_secret.encode('utf-8'), bytes(body), hashlib.sha256).hexdigest()
                return _secret_eq(expected, signature) and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
            signature_valid = bool(secret) and any(candidate and _secret_eq(secret, candidate) for candidate in (normalized_headers.get('authorization', '').removeprefix('Bearer ').strip(), normalized_headers.get('x-businessaios-webhook-secret', '')))
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        if not secret:
            return False
        if contract.verification_kind == 'slack_hmac_sha256_v0_or_shared_secret':
            signature, timestamp = normalized_headers.get('x-slack-signature', '').strip(), normalized_headers.get('x-slack-request-timestamp', '').strip()
            if signature or timestamp:
                if not signature or not timestamp or not timestamp.isascii() or not timestamp.isdecimal() or len(timestamp) > 20:
                    return False
                try:
                    if abs(time.time() - int(timestamp)) > int(contract.metadata.get('max_request_age_seconds') or 300):
                        return False
                    signing_base = b'v0:' + timestamp.encode('ascii') + b':' + bytes(body)
                except (OverflowError, ValueError, UnicodeEncodeError):
                    return False
                signature_valid = _secret_eq('v0=' + hmac.new(secret.encode('utf-8'), signing_base, hashlib.sha256).hexdigest(), signature)
                return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
            signature_valid = any(candidate and _secret_eq(secret, candidate) for candidate in (normalized_headers.get('authorization', '').removeprefix('Bearer ').strip(), normalized_headers.get('x-businessaios-webhook-secret', '')))
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        if contract.verification_kind == 'hmac_sha256_base64':
            expected = base64.b64encode(hmac.new(secret.encode('utf-8'), bytes(body), hashlib.sha256).digest()).decode('ascii')
            signature_valid = any(candidate and _secret_eq(expected, candidate) for candidate in (normalized_headers.get(str(name).lower(), '') for name in contract.header_names))
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        if contract.verification_kind in {'bearer_or_shared_secret', 'shared_secret_header', 'shared_secret_body_or_header'}:
            candidates = [normalized_headers.get('authorization', '').removeprefix('Bearer ').strip()] + [normalized_headers.get(str(name).lower(), '') for name in contract.header_names if str(name).lower() != 'authorization']
            if contract.verification_kind == 'shared_secret_body_or_header':
                candidates.append(str(ProviderPayloadNormalizers.parse_webhook_json(body).get('secret') or ''))
            signature_valid = any(candidate and _secret_eq(secret, candidate) for candidate in candidates)
            return signature_valid and self._recipient_matches(provider=provider, tenant_id=tenant_id, business_id=business_id, body=body)
        return False

    def response_body(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, body: bytes) -> str | None:
        if provider.provider_key != 'vk_messaging':
            return None
        event_type = str(ProviderPayloadNormalizers.parse_webhook_json(body).get('type') or '')
        return self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.confirmation_code') if event_type == 'confirmation' else 'ok'

    def verify_challenge(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, mode: str, verify_token: str, challenge: str) -> str | None:
        if provider.provider_key not in {'whatsapp_cloud', 'instagram_messaging', 'messenger_messaging'} or str(mode) != 'subscribe':
            return None
        expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.verify_token')
        return str(challenge) if expected and _secret_eq(expected, str(verify_token)) else None

    @staticmethod
    def _site_host(value: object) -> str:
        raw = str(value or "").strip()
        if not raw or any(character.isspace() for character in raw):
            return ""
        try:
            parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
            if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                return ""
        except ValueError:
            return ""
        return parsed.hostname.rstrip(".").lower()

    def _recipient_matches(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, body: bytes) -> bool:
        """Bind signed webhooks to the account or site configured for this tenant/business."""
        key = str(provider.provider_key)
        payload = ProviderPayloadNormalizers.parse_webhook_json(body)
        if key == "generic_website":
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f"{provider.connector_id}.site_domain")
            return bool(expected and self._site_host(expected) and self._site_host(payload.get("site_domain")) == self._site_host(expected))
        if key not in {'whatsapp_cloud', 'instagram_messaging', 'messenger_messaging', 'vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging', 'line_messaging', 'viber_messaging', 'wechat_messaging', 'kakaotalk_messaging'}:
            return True
        if key == 'whatsapp_cloud':
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.phone_number_id')
            entries = payload.get('entry')
            if not expected or not isinstance(entries, list) or not entries:
                return False
            observed: list[str] = []
            for entry in entries:
                if not isinstance(entry, Mapping):
                    return False
                changes = entry.get('changes')
                if not isinstance(changes, list) or not changes:
                    return False
                for change in changes:
                    value = change.get('value') if isinstance(change, Mapping) else None
                    metadata = value.get('metadata') if isinstance(value, Mapping) else None
                    recipient = metadata.get('phone_number_id') if isinstance(metadata, Mapping) else None
                    recipient_id = str(recipient or '').strip()
                    if not recipient_id or recipient_id != expected:
                        return False
                    observed.append(recipient_id)
            return bool(observed)
        if key in {'instagram_messaging', 'messenger_messaging'}:
            secret_name = 'ig_user_id' if key == 'instagram_messaging' else 'page_id'
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.{secret_name}')
            entries = payload.get('entry')
            if not expected or not isinstance(entries, list) or not entries:
                return False
            observed = [str(entry.get('id') or '').strip() for entry in entries if isinstance(entry, Mapping)]
            return bool(observed) and len(observed) == len(entries) and all(value == expected for value in observed)
        if key == 'slack_messaging':
            expected_team = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.team_id')
            expected_app = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.api_app_id')
            return bool(expected_team and expected_app and str(payload.get('team_id') or '').strip() == expected_team and str(payload.get('api_app_id') or '').strip() == expected_app)
        if key == 'discord_messaging':
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.application_id')
            return bool(expected and str(payload.get('application_id') or '').strip() == expected)
        if key == 'line_messaging':
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.bot_user_id')
            return bool(expected and str(payload.get('destination') or '').strip() == expected)
        if key == 'kakaotalk_messaging':
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.bot_id')
            bot = payload.get('bot')
            return bool(expected and isinstance(bot, Mapping) and str(bot.get('id') or '').strip() == expected)
        if key == 'wechat_messaging':
            expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.to_user_name')
            observed = payload.get('ToUserName') or payload.get('to_user_name')
            return bool(expected and str(observed or '').strip() == expected)
        if key == 'viber_messaging':
            # Viber's native callback has no bot-recipient field; the verified
            # X-Viber-Content-Signature uses this bot's account-specific auth token.
            return True
        if key == 'max_messaging':
            event_type, message = str(payload.get('update_type') or '').strip(), payload.get('message')
            if not event_type:
                return False
            if not isinstance(message, Mapping):
                return event_type not in {'message_created', 'message_edited', 'message_callback', 'comment_created', 'comment_edited'}
            recipient, sender = message.get('recipient'), message.get('sender')
            if not isinstance(recipient, Mapping) or not isinstance(sender, Mapping):
                return False
            chat_type = str(recipient.get('chat_type') or '')
            chat_id, sender_id = str(recipient.get('chat_id') or '').strip(), str(sender.get('user_id') or '').strip()
            observed = str(recipient.get('user_id') or '').strip()
            if chat_type not in {'dialog', 'chat', 'channel'} or not chat_id.isdecimal() or not sender_id.isdecimal() or sender.get('is_bot') is True:
                return False
            if chat_type == 'dialog' or observed:
                expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.bot_id')
                return bool(expected and expected.isdecimal() and observed == expected)
            return True
        expected = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.group_id')
        observed = str(payload.get('group_id') or '').strip()
        return bool(expected and observed and observed == expected)

    def _secret_field(self, provider: ProviderDefinition) -> str:
        return next((field.secret_name for preferred_kind in ('signing_secret', 'token', 'api_key', 'password') for field in provider.secret_fields if field.secret_kind == preferred_kind), provider.secret_fields[0].secret_name if provider.secret_fields else 'secret')

    def _read_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str | None:
        try:
            return self.secret_vault.get(SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)).decode('utf-8').strip()
        except KeyError:
            return None
        except Exception:
            return ''

__all__ = ['CANON_PROVIDER_WEBHOOK_RUNTIME', 'ProviderWebhookRuntime', 'RAW_SIGNATURE_FIRST_PROVIDER_KEYS']
