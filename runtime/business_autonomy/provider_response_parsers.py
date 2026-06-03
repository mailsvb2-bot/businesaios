from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition

CANON_PROVIDER_RESPONSE_PARSERS = True


@dataclass(frozen=True)
class ProviderResponseParsers:
    def parse(self, *, provider: ProviderDefinition, operation: str, response: Mapping[str, Any]) -> dict[str, Any]:
        provider_key = str(provider.provider_key)
        status_code = self._coerce_int(response.get('http_status'))
        raw_body = str(response.get('response_body') or '')
        body = self._parse_json(raw_body)
        normalized = {
            'provider_key': provider_key,
            'operation': str(operation),
            'http_status': status_code,
            'ok': status_code is not None and 200 <= status_code < 300,
            'resource_count': self._resource_count(provider_key=provider_key, body=body),
            'resource_id': self._resource_id(provider_key=provider_key, body=body),
            'next_cursor': self._next_cursor(provider_key=provider_key, body=body),
            'error_code': self._error_code(provider_key=provider_key, body=body),
            'error_message': self._error_message(provider_key=provider_key, body=body),
            'body_keys': tuple(sorted(body.keys())) if isinstance(body, dict) else (),
            'normalized_preview': self._preview(body),
        }
        return normalized

    def describe(self, *, provider: ProviderDefinition) -> dict[str, Any]:
        families = {
            'telegram_bot': ('ok', 'result', 'description'),
            'whatsapp_cloud': ('messages', 'contacts', 'error'),
            'shopify': ('orders', 'products', 'admin_graphql_api_id', 'errors', 'page_info'),
            'woocommerce': ('id', 'code', 'message', 'data'),
            'hubspot': ('results', 'paging', 'status', 'message'),
            'meta_ads': ('data', 'paging', 'error'),
            'google_ads': ('results', 'nextPageToken', 'error'),
            'tiktok_ads': ('data', 'page_info', 'message', 'code'),
        }
        return {
            'provider_key': provider.provider_key,
            'supported': True,
            'known_fields': families.get(provider.provider_key, ('status', 'data', 'error')),
            'response_history_endpoint': '/control-plane/provider-runtime/sync-history',
        }

    def _parse_json(self, raw: str) -> Any:
        raw = raw.strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {'_raw_text': raw[:2000]}

    def _resource_count(self, *, provider_key: str, body: Any) -> int | None:
        if isinstance(body, dict):
            for key in ('results', 'data', 'messages', 'orders', 'products'):
                value = body.get(key)
                if isinstance(value, list):
                    return len(value)
            if provider_key in {'shopify', 'woocommerce'} and 'id' in body:
                return 1
        if isinstance(body, list):
            return len(body)
        return None

    def _resource_id(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            for key in ('id', 'admin_graphql_api_id', 'message_id', 'campaign_id'):
                value = body.get(key)
                if value not in {None, ''}:
                    return str(value)
            if provider_key == 'telegram_bot' and isinstance(body.get('result'), dict):
                value = body['result'].get('message_id') or body['result'].get('id')
                if value not in {None, ''}:
                    return str(value)
        return None

    def _next_cursor(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            if isinstance(body.get('paging'), dict):
                paging = body['paging']
                for key in ('next', 'after'):
                    value = paging.get(key)
                    if value not in {None, ''}:
                        return str(value)
            if isinstance(body.get('page_info'), dict):
                value = body['page_info'].get('cursor') or body['page_info'].get('next_cursor')
                if value not in {None, ''}:
                    return str(value)
            for key in ('nextPageToken', 'next_page_token', 'page_token'):
                value = body.get(key)
                if value not in {None, ''}:
                    return str(value)
        return None

    def _error_code(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            if isinstance(body.get('error'), dict):
                err = body['error']
                return str(err.get('code') or err.get('type') or err.get('status') or '') or None
            for key in ('code', 'status', 'error_code'):
                value = body.get(key)
                if isinstance(value, (int, str)) and str(value).strip() and (provider_key != 'telegram_bot' or key != 'status'):
                    return str(value)
        return None

    def _error_message(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            if isinstance(body.get('error'), dict):
                err = body['error']
                return str(err.get('message') or err.get('error_user_msg') or '') or None
            for key in ('message', 'description', 'error_description'):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _preview(self, body: Any) -> Any:
        if isinstance(body, dict):
            preview = {}
            for key, value in list(body.items())[:8]:
                if isinstance(value, (str, int, float, bool)) or value is None:
                    preview[key] = value
                elif isinstance(value, list):
                    preview[key] = f'list[{len(value)}]'
                elif isinstance(value, dict):
                    preview[key] = f'dict[{len(value)}]'
                else:
                    preview[key] = type(value).__name__
            return preview
        if isinstance(body, list):
            return f'list[{len(body)}]'
        return body

    def _coerce_int(self, value: Any) -> int | None:
        try:
            return None if value in {None, ''} else int(value)
        except Exception:
            return None


__all__ = ['CANON_PROVIDER_RESPONSE_PARSERS', 'ProviderResponseParsers']
