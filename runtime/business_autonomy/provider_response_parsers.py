from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition

CANON_PROVIDER_RESPONSE_PARSERS = True


@dataclass(frozen=True)
class ProviderResponseParsers:
    def parse(self, *, provider: ProviderDefinition, operation: str, response: Mapping[str, Any]) -> dict[str, Any]:
        provider_key, status_code, raw_body = str(provider.provider_key), self._coerce_int(response.get('http_status')), str(response.get('response_body') or '')
        body = self._parse_json(raw_body)
        headers = {str(key).lower(): str(value) for key, value in dict(response.get('response_headers') or {}).items()} if isinstance(response.get('response_headers'), Mapping) else {}
        error_code = self._error_code(provider_key=provider_key, body=body)
        rate_limited = status_code == 429 or (provider_key == 'vk_messaging' and error_code == '6') or (provider_key == 'slack_messaging' and error_code in {'rate_limited', 'ratelimited'})
        max_media_not_ready = provider_key == 'max_messaging' and str(error_code or '').casefold() in {'attachment.not.ready', 'media.prepared'}
        max_media_token_rejected = provider_key == 'max_messaging' and str(error_code or '').casefold() in {'attachment.invalid', 'attachment.not.found', 'attachment.not_found', 'invalid_attachment', 'invalid_token', 'media.not.found'}
        retry_after_seconds = self._retry_after_seconds(headers=headers, body=body)
        error_category = 'rate_limit' if rate_limited else ('media_preparation' if str(error_code or '').casefold() == 'media.prepared' else ('media_not_ready' if max_media_not_ready else ('media_token_rejected' if max_media_token_rejected else ('provider_unavailable' if status_code is not None and status_code >= 500 else None))))
        normalized = {
            'provider_key': provider_key,
            'operation': str(operation),
            'http_status': status_code,
            'ok': status_code is not None and 200 <= status_code < 300 and not error_code,
            'resource_count': self._resource_count(provider_key=provider_key, body=body),
            'resource_id': self._resource_id(provider_key=provider_key, body=body, headers=headers),
            'next_cursor': self._next_cursor(provider_key=provider_key, body=body),
            'error_code': error_code,
            'error_message': self._error_message(provider_key=provider_key, body=body), 'error_category': error_category,
            'retryable': rate_limited or max_media_not_ready or max_media_token_rejected or (status_code is not None and status_code >= 500), 'retry_after_seconds': retry_after_seconds, 'delivery_state': ('accepted' if 200 <= status_code < 300 and not error_code else 'rejected') if str(operation) in {'message_send', 'communications_write'} and status_code is not None else None,
            'body_keys': tuple(sorted(body.keys())) if isinstance(body, dict) else (),
            'normalized_preview': self._preview(body),
        }
        return normalized

    def describe(self, *, provider: ProviderDefinition) -> dict[str, Any]:
        families = {
            'telegram_bot': ('ok', 'result', 'description'),
            'whatsapp_cloud': ('messages', 'contacts', 'error'), 'instagram_messaging': ('recipient_id', 'message_id', 'error'), 'messenger_messaging': ('recipient_id', 'message_id', 'error'), 'vk_messaging': ('response', 'error'), 'max_messaging': ('messages', 'code', 'message'), 'slack_messaging': ('ok', 'channel', 'ts', 'message', 'error'), 'discord_messaging': ('id', 'channel_id', 'content', 'code', 'message'), 'line_messaging': ('userId', 'basicId', 'displayName', 'message'), 'viber_messaging': ('status', 'status_message', 'id', 'message_token'),
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
            for key in ('results', 'result', 'data', 'messages', 'orders', 'products'):
                value = body.get(key)
                if isinstance(value, list):
                    return len(value)
            if provider_key in {'shopify', 'woocommerce'} and 'id' in body:
                return 1
        if isinstance(body, list):
            return len(body)
        return None

    def _resource_id(self, *, provider_key: str, body: Any, headers: Mapping[str, str] | None = None) -> str | None:
        if isinstance(body, dict):
            for key in ('id', 'admin_graphql_api_id', 'message_id', 'message_token', 'campaign_id'):
                value = body.get(key)
                if value not in {None, ''}:
                    return str(value)
            if provider_key == 'telegram_bot' and isinstance(body.get('result'), dict):
                value = body['result'].get('message_id') or body['result'].get('id')
                if value not in {None, ''}:
                    return str(value)
            if provider_key == 'vk_messaging' and body.get('response') is not None and body.get('response') != '' and not isinstance(body.get('response'), dict | list):
                return str(body['response'])
            if provider_key == 'max_messaging':
                source = body.get('message') if isinstance(body.get('message'), dict) else (body.get('messages')[0] if isinstance(body.get('messages'), list) and body.get('messages') and isinstance(body.get('messages')[0], dict) else {})
                value = source.get('message_id') or source.get('id')
                if value not in {None, ''}:
                    return str(value)
            if provider_key == 'slack_messaging':
                source = body.get('message') if isinstance(body.get('message'), dict) else {}
                value = body.get('ts') or source.get('ts')
                if value not in {None, ''}:
                    return str(value)
        return (str(headers.get('x-line-accepted-request-id') or headers.get('x-line-request-id') or '') or None) if provider_key == 'line_messaging' and isinstance(headers, Mapping) else None

    def _next_cursor(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            if isinstance(body.get('paging'), dict):
                paging, value = body['paging'], body['paging'].get('next')
                if isinstance(value, dict):
                    value = value.get('after')
                return str(value or paging.get('after') or '') or None
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
            if provider_key == 'viber_messaging' and body.get('status') not in {None, 0, '0'}:
                return str(body.get('status'))
            if provider_key == 'slack_messaging' and body.get('ok') is False:
                return str(body.get('error') or 'slack_api_error')
            if isinstance(body.get('error'), dict):
                err = body['error']
                return str(err.get('code') or err.get('error_code') or err.get('type') or err.get('status') or '') or None
            for key in ('code', 'status', 'error_code'):
                value = body.get(key)
                if isinstance(value, int | str) and str(value).strip() and (provider_key not in {'telegram_bot', 'viber_messaging'} or key != 'status'):
                    return str(value)
        return None

    def _error_message(self, *, provider_key: str, body: Any) -> str | None:
        if isinstance(body, dict):
            if isinstance(body.get('error'), dict):
                err = body['error']
                return str(err.get('message') or err.get('error_msg') or err.get('error_user_msg') or '') or None
            for key in ('message', 'description', 'error_description'):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _retry_after_seconds(self, *, headers: Mapping[str, str], body: Any) -> int | None:
        value = body.get('retry_after') if isinstance(body, dict) else None
        if value in {None, ''}:
            value = headers.get('retry-after')
        try:
            return max(0, int(ceil(float(value)))) if value not in {None, ''} else None
        except (TypeError, ValueError):
            return None

    def _preview(self, body: Any) -> Any:
        if isinstance(body, dict):
            preview = {}
            for key, value in list(body.items())[:8]:
                if isinstance(value, str | int | float | bool) or value is None:
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
