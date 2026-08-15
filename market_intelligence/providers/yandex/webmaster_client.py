from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.parse import quote

from market_intelligence.providers.yandex.config import WebmasterConfig
from market_intelligence.transport import ExternalProviderError, ReadOnlyHttpTransport


class WebmasterClient:
    def __init__(self, config: WebmasterConfig, *, transport: ReadOnlyHttpTransport | None = None) -> None:
        self.config = config
        self._transport = transport or ReadOnlyHttpTransport(
            provider_key='yandex_webmaster', timeout_seconds=config.timeout_seconds
        )

    def popular_queries(self, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        if limit < 1 or limit > 500:
            raise ValueError('Webmaster limit must be in [1, 500]')
        host_id = quote(self.config.host_id.strip(), safe=':')
        response = self._transport.get(
            f'{self.config.base_url}/v4/user/{self.config.user_id}/hosts/{host_id}/search-queries/popular',
            params={
                'order_by': self.config.order_by,
                'query_indicator': 'AVG_SHOW_POSITION',
                'device_type_indicator': self.config.device_type,
                'limit': limit,
                'offset': 0,
            },
            headers={
                'Authorization': f'OAuth {self.config.oauth_token}',
                'Accept': 'application/json',
            },
        )
        try:
            body = json.loads(response.text or '{}')
        except json.JSONDecodeError as exc:
            raise ExternalProviderError(
                'yandex_webmaster returned invalid JSON', provider_key='yandex_webmaster'
            ) from exc
        rows = body.get('queries') if isinstance(body, Mapping) else None
        if not isinstance(rows, list):
            raise ExternalProviderError(
                'yandex_webmaster response is missing queries', provider_key='yandex_webmaster'
            )
        return tuple(dict(row) for row in rows if isinstance(row, Mapping))
