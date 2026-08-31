from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_webhook_messaging_bridge import (
    messaging_ingress_to_metadata,
    resolve_provider_webhook_messaging_ingress,
)

CANON_PROVIDER_WEBHOOK_ROUTE_REGISTRY = True


_PROVIDER_HEADERS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    'shopify': {'event_key_headers': ('X-Shopify-Webhook-Id', 'X-Request-Id'), 'topic_headers': ('X-Shopify-Topic',), 'source_headers': ('X-Shopify-Shop-Domain',)},
    'telegram_bot': {'event_key_headers': ('X-Telegram-Update-Id', 'X-Request-Id'), 'topic_headers': ('X-Telegram-Event',), 'source_headers': ()},
    'whatsapp_cloud': {'event_key_headers': ('X-Hub-Signature-256', 'X-Request-Id'), 'topic_headers': ('X-Hub-Topic',), 'source_headers': ()},
    'generic_website': {'event_key_headers': ('X-Event-Id', 'X-Request-Id'), 'topic_headers': ('X-Topic', 'X-Webhook-Topic'), 'source_headers': ('X-Origin-Site',)},
    'wordpress': {'event_key_headers': ('X-WordPress-Event-Id', 'X-Request-Id'), 'topic_headers': ('X-WordPress-Topic', 'X-Webhook-Topic'), 'source_headers': ('X-WordPress-Site',)},
}


@dataclass(frozen=True)
class ProviderWebhookRouteRegistry:
    normalizers: ProviderPayloadNormalizers = field(default_factory=ProviderPayloadNormalizers)

    def describe(self, provider: ProviderDefinition) -> dict[str, Any]:
        path = f'/providers/webhook/{{tenant_id}}/{{business_id}}/{provider.provider_key}'
        headers = dict(_PROVIDER_HEADERS.get(provider.provider_key) or {'event_key_headers': ('X-Event-Id', 'X-Request-Id'), 'topic_headers': ('X-Topic', 'X-Webhook-Topic'), 'source_headers': ()})
        return {'provider_key': provider.provider_key, 'route_family': 'provider_webhook_ingress', 'path_template': path, 'method': 'POST', **headers}

    def extract(self, provider: ProviderDefinition, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        return self.extract_many(provider, headers, body)[0]

    def extract_many(self, provider: ProviderDefinition, headers: Mapping[str, str], body: bytes) -> tuple[dict[str, Any], ...]:
        raw_payload = self.normalizers.parse_webhook_json(body)
        if provider.provider_key == 'line_messaging' and isinstance(raw_payload.get('events'), list):
            event_payloads = [dict(raw_payload, events=[event]) for event in raw_payload['events'] if isinstance(event, Mapping)]
            if event_payloads:
                routes = []
                for payload in event_payloads:
                    route = self._extract(provider, headers, json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
                    stable_event = dict(payload['events'][0]); stable_event.pop('deliveryContext', None)
                    route['payload_digest'] = hashlib.sha256(json.dumps(dict(payload, events=[stable_event]), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
                    routes.append(route)
                return tuple(routes)
        return (self._extract(provider, headers, body),)

    def _extract(self, provider: ProviderDefinition, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        route = self.describe(provider)
        normalized_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
        normalized_payload = self.normalizers.normalize_webhook_payload(provider=provider, headers=normalized_headers, body=body)
        raw_payload = self.normalizers.parse_webhook_json(body)
        event_hint = str(normalized_payload.get('event_key_hint') or '')
        event_key = (event_hint or self._first(normalized_headers, route['event_key_headers'])) if provider.provider_key in {'line_messaging', 'viber_messaging'} else (self._first(normalized_headers, route['event_key_headers']) or event_hint)
        event_key = event_key or f"{provider.provider_key}:{hashlib.sha256(bytes(body)).hexdigest()[:24]}"
        return {
            'event_key': event_key,
            'topic': self._first(normalized_headers, route['topic_headers']) or str(normalized_payload.get('topic') or ''),
            'source_ref': self._first(normalized_headers, route.get('source_headers', ())) or str(normalized_payload.get('source_ref') or ''),
            'resource_id': str(normalized_payload.get('resource_id') or ''),
            'payload_digest': hashlib.sha256(bytes(body)).hexdigest(),
            'messaging_ingress': messaging_ingress_to_metadata(resolve_provider_webhook_messaging_ingress(provider=provider, normalized_payload=raw_payload)),
        }

    @staticmethod
    def _first(headers: Mapping[str, str], names: tuple[str, ...]) -> str:
        lower = {k.lower(): v for k, v in headers.items()}
        for name in names:
            value = lower.get(str(name).lower(), '')
            if str(value).strip():
                return str(value).strip()
        return ''


__all__ = ['CANON_PROVIDER_WEBHOOK_ROUTE_REGISTRY', 'ProviderWebhookRouteRegistry']
