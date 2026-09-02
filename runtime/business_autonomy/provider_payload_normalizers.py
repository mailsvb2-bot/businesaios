from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition

CANON_PROVIDER_PAYLOAD_NORMALIZERS = True

@dataclass(frozen=True)
class ProviderPayloadNormalizers:
    def normalize_outbound(self, *, provider: ProviderDefinition, operation: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = dict(payload or {})
        key = provider.provider_key
        operation = str(operation or '').strip()
        if key == 'telegram_bot':
            return {'chat_id': str(raw.get('chat_id') or '{chat_id}'), 'text': str(raw.get('text') or raw.get('message') or '')} if operation == 'communications_write' else raw
        if key == 'whatsapp_cloud':
            return {'messaging_product': raw.get('messaging_product') or 'whatsapp', 'to': str(raw.get('to') or '{recipient_phone}'), 'type': str(raw.get('type') or 'text'), 'text': dict(raw.get('text') or {'body': str(raw.get('body') or raw.get('message') or '')}), **{k: v for k, v in raw.items() if k not in {'messaging_product', 'to', 'type', 'text', 'body', 'message'}}}
        if operation in {'communications_write', 'message_send'} and key in {'line_messaging', 'viber_messaging'}:
            return {'to': str(raw.get('to') or raw.get('user_id') or '{recipient_id}'), 'messages': [{'type': 'text', 'text': str(raw.get('text') or raw.get('message') or '')}]} if key == 'line_messaging' else {'receiver': str(raw.get('receiver') or raw.get('user_id') or '{recipient_id}'), 'type': 'text', 'sender': {'name': str(raw.get('sender_name') or '{sender_name}')}, 'text': str(raw.get('text') or raw.get('message') or '')}
        if operation in {'communications_write', 'message_send'} and key in {'vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging', 'instagram_messaging', 'messenger_messaging'}:
            if key in {'instagram_messaging', 'messenger_messaging'}:
                return {'recipient_id': str(raw.get('recipient_id') or raw.get('psid') or raw.get('ig_scoped_id') or raw.get('user_id') or '{recipient_id}'), 'text': str(raw.get('text') or raw.get('message') or '')}
            if key == 'slack_messaging':
                return {'channel': str(raw.get('channel') or raw.get('channel_id') or '{channel_id}'), 'text': str(raw.get('text') or raw.get('message') or '')}
            if key == 'discord_messaging':
                return {'channel_id': str(raw.get('channel_id') or '{channel_id}'), 'text': str(raw.get('text') or raw.get('message') or '')}
            return {'peer_id': str(raw.get('peer_id') or raw.get('chat_id') or raw.get('user_id') or '{peer_id}'), 'random_id': int(raw.get('random_id') or 0), 'message': str(raw.get('message') or raw.get('text') or ''), 'group_id': str(raw.get('group_id') or '{group_id}')} if key == 'vk_messaging' else {'chat_id': str(raw.get('chat_id') or ''), 'user_id': str(raw.get('user_id') or ''), 'text': str(raw.get('text') or raw.get('message') or '')}
        if key in {'shopify', 'woocommerce'}:
            if operation.endswith('catalog_sync'):
                return {'cursor': raw.get('cursor') or '', 'limit': int(raw.get('limit') or 100), **{k: v for k, v in raw.items() if k not in {'cursor', 'limit'}}}
            if 'refund' in operation:
                return {'order_id': raw.get('order_id') or '{order_id}', 'amount': raw.get('amount') or 0, **{k: v for k, v in raw.items() if k not in {'order_id', 'amount'}}}
            return raw
        if key == 'hubspot':
            if operation == 'contact_upsert':
                props = dict(raw.get('properties') or {})
                return {'properties': props or {'email': raw.get('email') or '{email}'}, **{k: v for k, v in raw.items() if k != 'properties'}}
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
        parsed = self.parse_webhook_json(body)
        if (key := provider.provider_key) == 'shopify':
            return {'topic': header_map.get('x-shopify-topic', ''), 'source_ref': header_map.get('x-shopify-shop-domain', ''), 'resource_id': str(parsed.get('id') or parsed.get('admin_graphql_api_id') or ''), 'event_key_hint': header_map.get('x-shopify-webhook-id', '')}
        if key == 'telegram_bot':
            message = parsed.get('message') if isinstance(parsed.get('message'), Mapping) else {}
            return {'topic': 'telegram_update', 'source_ref': str((message.get('chat') if isinstance(message.get('chat'), Mapping) else {}).get('id') or ''), 'resource_id': str(parsed.get('update_id') or ''), 'event_key_hint': str(parsed.get('update_id') or '')}
        if key == 'whatsapp_cloud':
            entry = parsed.get('entry') if isinstance(parsed.get('entry'), list) and parsed.get('entry') else {}
            entry0 = entry[0] if isinstance(entry, list) and entry else {}
            return {'topic': header_map.get('x-hub-topic', '') or 'whatsapp_event', 'source_ref': str(entry0.get('id') or ''), 'resource_id': str(entry0.get('id') or ''), 'event_key_hint': header_map.get('x-request-id', '')}
        if key == 'vk_messaging':
            event_id = str(parsed.get('event_id') or '')
            return {'topic': str(parsed.get('type') or ''), 'source_ref': str(parsed.get('group_id') or ''), 'resource_id': event_id, 'event_key_hint': event_id}
        if key == 'slack_messaging':
            event = parsed.get('event') if isinstance(parsed.get('event'), Mapping) else {}
            event_id = str(parsed.get('event_id') or event.get('client_msg_id') or event.get('event_ts') or event.get('ts') or '')
            return {'topic': str(event.get('type') or parsed.get('type') or ''), 'source_ref': str(parsed.get('team_id') or event.get('channel') or ''), 'resource_id': event_id, 'event_key_hint': event_id}
        if key == 'line_messaging':
            event = parsed.get('events')[0] if isinstance(parsed.get('events'), list) and parsed.get('events') and isinstance(parsed.get('events')[0], Mapping) else {}
            source = event.get('source') if isinstance(event.get('source'), Mapping) else {}
            message = event.get('message') if isinstance(event.get('message'), Mapping) else {}
            event_id = str(event.get('webhookEventId') or message.get('id') or '')
            return {'topic': str(event.get('type') or ''), 'source_ref': str(source.get('userId') or source.get('groupId') or source.get('roomId') or ''), 'resource_id': event_id, 'event_key_hint': event_id}
        if key == 'viber_messaging':
            source = parsed.get('sender') if isinstance(parsed.get('sender'), Mapping) else parsed.get('user') if isinstance(parsed.get('user'), Mapping) else {}
            event_id = str(parsed.get('message_token') or parsed.get('timestamp') or '')
            return {'topic': str(parsed.get('event') or ''), 'source_ref': str(source.get('id') or parsed.get('user_id') or ''), 'resource_id': event_id, 'event_key_hint': event_id}
        if key in {'generic_website', 'wordpress'}:
            return {'topic': header_map.get('x-topic', '') or header_map.get('x-webhook-topic', ''), 'source_ref': header_map.get('x-origin-site', '') or header_map.get('x-wordpress-site', ''), 'resource_id': str(parsed.get('id') or parsed.get('slug') or ''), 'event_key_hint': header_map.get('x-event-id', '') or header_map.get('x-wordpress-event-id', '')}
        return {'topic': '', 'source_ref': '', 'resource_id': '', 'event_key_hint': ''}
    @staticmethod
    def parse_webhook_json(body: bytes) -> Mapping[str, Any]:
        if not body:
            return {}
        try:
            value = json.loads(body.decode('utf-8'))
        except Exception:
            return {}
        return value if isinstance(value, Mapping) else {}

__all__ = ['CANON_PROVIDER_PAYLOAD_NORMALIZERS', 'ProviderPayloadNormalizers']
