from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition

CANON_PROVIDER_PAYLOAD_NORMALIZERS = True


@dataclass(frozen=True)
class ProviderPayloadNormalizers:
    def normalize_outbound(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = dict(payload or {})
        key = provider.provider_key
        operation = str(operation or '').strip()
        if key == 'telegram_bot':
            if operation == 'communications_write':
                return {'chat_id': str(raw.get('chat_id') or '{chat_id}'), 'text': str(raw.get('text') or raw.get('message') or '')}
            return raw
        if key == 'whatsapp_cloud':
            return {
                'messaging_product': raw.get('messaging_product') or 'whatsapp',
                'to': str(raw.get('to') or '{recipient_phone}'),
                'type': str(raw.get('type') or 'text'),
                'text': dict(raw.get('text') or {'body': str(raw.get('body') or raw.get('message') or '')}),
                **{k: v for k, v in raw.items() if k not in {'messaging_product', 'to', 'type', 'text', 'body', 'message'}},
            }
        if key in {'shopify', 'woocommerce'}:
            if operation.endswith('catalog_sync'):
                return {'cursor': raw.get('cursor') or '', 'limit': int(raw.get('limit') or 100), **{k: v for k, v in raw.items() if k not in {'cursor', 'limit'}}}
            if 'refund' in operation:
                return {'order_id': raw.get('order_id') or '{order_id}', 'amount': raw.get('amount') or 0, **{k: v for k, v in raw.items() if k not in {'order_id', 'amount'}}}
            return raw
        if key == 'hubspot':
            if operation == 'contact_upsert':
                props = dict(raw.get('properties') or {})
                return {'properties': props or {'email': raw.get('email') or '{email}'}, **{k: v for k, v in raw.items() if k not in {'properties'}}}
            return raw
        if key in {'meta_ads', 'google_ads', 'tiktok_ads'}:
            normalized = dict(raw)
            normalized.setdefault('campaign_id', raw.get('campaign_id') or '{campaign_id}')
            if 'budget' in operation and 'budget' not in normalized:
                normalized['budget'] = raw.get('amount') or 0
            return normalized
        return raw

    def normalize_webhook_payload(self, *, provider: ProviderDefinition, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        header_map = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
        parsed = self._try_parse_json(body)
        key = provider.provider_key
        if key == 'shopify':
            return {
                'topic': header_map.get('x-shopify-topic', ''),
                'source_ref': header_map.get('x-shopify-shop-domain', ''),
                'resource_id': str(parsed.get('id') or parsed.get('admin_graphql_api_id') or ''),
                'event_key_hint': header_map.get('x-shopify-webhook-id', ''),
            }
        if key == 'telegram_bot':
            message = parsed.get('message') if isinstance(parsed.get('message'), Mapping) else {}
            chat = message.get('chat') if isinstance(message, Mapping) else {}
            return {
                'topic': 'telegram_update',
                'source_ref': str((chat or {}).get('id') or ''),
                'resource_id': str(parsed.get('update_id') or ''),
                'event_key_hint': str(parsed.get('update_id') or ''),
            }
        if key == 'whatsapp_cloud':
            entry = parsed.get('entry') if isinstance(parsed.get('entry'), list) and parsed.get('entry') else {}
            entry0 = entry[0] if isinstance(entry, list) and entry else {}
            return {
                'topic': header_map.get('x-hub-topic', '') or 'whatsapp_event',
                'source_ref': str(entry0.get('id') or ''),
                'resource_id': str(entry0.get('id') or ''),
                'event_key_hint': header_map.get('x-request-id', ''),
            }
        if key in {'generic_website', 'wordpress'}:
            return {
                'topic': header_map.get('x-topic', '') or header_map.get('x-webhook-topic', ''),
                'source_ref': header_map.get('x-origin-site', '') or header_map.get('x-wordpress-site', ''),
                'resource_id': str(parsed.get('id') or parsed.get('slug') or ''),
                'event_key_hint': header_map.get('x-event-id', '') or header_map.get('x-wordpress-event-id', ''),
            }
        return {'topic': '', 'source_ref': '', 'resource_id': '', 'event_key_hint': ''}

    @staticmethod
    def _try_parse_json(body: bytes) -> Mapping[str, Any]:
        if not body:
            return {}
        try:
            value = json.loads(body.decode('utf-8'))
        except Exception:
            return {}
        return value if isinstance(value, Mapping) else {}


__all__ = ['CANON_PROVIDER_PAYLOAD_NORMALIZERS', 'ProviderPayloadNormalizers']
