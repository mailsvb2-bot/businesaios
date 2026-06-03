from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

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

    def extract(self, provider: ProviderDefinition, headers: Mapping[str, str], body: bytes) -> dict[str, str]:
        route = self.describe(provider)
        normalized_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
        normalized_payload = self.normalizers.normalize_webhook_payload(provider=provider, headers=normalized_headers, body=body)
        raw_payload = self._try_parse_json(body)
        event_key = self._first(normalized_headers, route['event_key_headers']) or str(normalized_payload.get('event_key_hint') or '') or f"{provider.provider_key}:{abs(hash(bytes(body))) % 1000000000}"
        topic = self._first(normalized_headers, route['topic_headers']) or str(normalized_payload.get('topic') or '')
        source_ref = self._first(normalized_headers, route.get('source_headers', ())) or str(normalized_payload.get('source_ref') or '')
        resource_id = str(normalized_payload.get('resource_id') or '')
        messaging_ingress = resolve_provider_webhook_messaging_ingress(provider=provider, normalized_payload=raw_payload)
        return {
            'event_key': event_key,
            'topic': topic,
            'source_ref': source_ref,
            'resource_id': resource_id,
            'messaging_ingress': messaging_ingress_to_metadata(messaging_ingress),
        }

    @staticmethod
    def _try_parse_json(body: bytes) -> Mapping[str, Any]:
        if not body:
            return {}
        try:
            value = json.loads(body.decode('utf-8'))
        except Exception:
            return {}
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _first(headers: Mapping[str, str], names: tuple[str, ...]) -> str:
        lower = {k.lower(): v for k, v in headers.items()}
        for name in names:
            value = lower.get(str(name).lower(), '')
            if str(value).strip():
                return str(value).strip()
        return ''


__all__ = ['CANON_PROVIDER_WEBHOOK_ROUTE_REGISTRY', 'ProviderWebhookRouteRegistry']
