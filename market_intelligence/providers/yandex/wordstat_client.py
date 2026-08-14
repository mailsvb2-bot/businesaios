from __future__ import annotations

import json
from collections.abc import Mapping

from market_intelligence.providers.yandex.config import WordstatConfig
from market_intelligence.transport import ExternalProviderError, ReadOnlyHttpTransport


class WordstatClient:
    def __init__(self, config: WordstatConfig, *, transport: ReadOnlyHttpTransport | None = None) -> None:
        self.config = config
        self._transport = transport or ReadOnlyHttpTransport(
            provider_key='yandex_wordstat', timeout_seconds=config.timeout_seconds
        )

    @staticmethod
    def _phrase(value: str) -> str:
        phrase = value.strip()
        if not phrase:
            raise ValueError('Wordstat phrase must not be blank')
        return phrase

    def top_requests(self, *, phrase: str) -> tuple[dict[str, object], ...]:
        payload: dict[str, object] = {
            'phrase': self._phrase(phrase),
            'devices': list(self.config.devices),
        }
        if self.config.regions:
            payload['regions'] = list(self.config.regions)
        response = self._transport.post_json(
            f'{self.config.base_url}/v1/topRequests',
            payload=payload,
            headers={
                'Authorization': f'Bearer {self.config.oauth_token}',
                'Content-Type': 'application/json',
            },
        )
        try:
            body = json.loads(response.text or '{}')
        except json.JSONDecodeError as exc:
            raise ExternalProviderError(
                'yandex_wordstat returned invalid JSON', provider_key='yandex_wordstat'
            ) from exc
        rows = body.get('topRequests') if isinstance(body, Mapping) else None
        if not isinstance(rows, list):
            raise ExternalProviderError(
                'yandex_wordstat response is missing topRequests', provider_key='yandex_wordstat'
            )
        return tuple(dict(row) for row in rows if isinstance(row, Mapping))
