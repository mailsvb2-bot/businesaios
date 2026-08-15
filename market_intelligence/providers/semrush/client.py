from __future__ import annotations

from collections.abc import Sequence

from market_intelligence.providers.semrush.config import SemrushConfig
from market_intelligence.providers.semrush.parser import parse_semrush_table
from market_intelligence.transport import ReadOnlyHttpTransport


_KEYWORD_EXPORT_COLUMNS = 'Ph,Nq,Cp,Co,Nr,Kd'
_DOMAIN_ORGANIC_EXPORT_COLUMNS = 'Ph,Po,Ur,Tr'


class SemrushClient:
    """Minimal Semrush v3 report client.

    v3 remains deliberately explicit because Semrush API keys are version-bound.
    Adding v4 should be a sibling implementation, not a silent endpoint switch.
    """

    def __init__(self, config: SemrushConfig, *, transport: ReadOnlyHttpTransport | None = None) -> None:
        self.config = config
        self._transport = transport or ReadOnlyHttpTransport(provider_key='semrush', timeout_seconds=config.timeout_seconds)

    def _report(self, report_type: str, **params: object) -> list[dict[str, str]]:
        payload = {'key': self.config.api_key, 'type': report_type, 'export_escape': 1, **params}
        response = self._transport.get(self.config.base_url_v3, params=payload)
        return parse_semrush_table(response.text)

    @staticmethod
    def _validated_phrase(phrase: str) -> str:
        normalized = phrase.strip()
        if not normalized:
            raise ValueError('Semrush phrase must not be blank')
        if ';' in normalized:
            raise ValueError('Semrush phrase must not contain the batch delimiter ";"')
        return normalized

    @staticmethod
    def _validated_database(database: str) -> str:
        normalized = database.strip()
        if not normalized:
            raise ValueError('Semrush database must not be blank')
        return normalized

    def keyword_overview(self, *, phrase: str, database: str) -> list[dict[str, str]]:
        return self._report(
            'phrase_this',
            phrase=self._validated_phrase(phrase),
            database=self._validated_database(database),
            export_columns=_KEYWORD_EXPORT_COLUMNS,
        )

    def keyword_overviews(self, *, phrases: Sequence[str], database: str) -> list[dict[str, str]]:
        normalized = [self._validated_phrase(phrase) for phrase in phrases]
        if not normalized:
            return []
        database = self._validated_database(database)
        rows: list[dict[str, str]] = []
        # Semrush v3 Batch Keyword Overview accepts at most 100 phrases per call.
        for offset in range(0, len(normalized), 100):
            batch = normalized[offset:offset + 100]
            rows.extend(self._report(
                'phrase_these',
                phrase=';'.join(batch),
                database=database,
                export_columns=_KEYWORD_EXPORT_COLUMNS,
            ))
        return rows

    def domain_organic_keywords(self, *, domain: str, database: str, limit: int = 100) -> list[dict[str, str]]:
        domain = domain.strip()
        if not domain:
            raise ValueError('Semrush domain must not be blank')
        if limit < 1 or limit > 10_000:
            raise ValueError('limit must be in [1, 10000]')
        return self._report(
            'domain_organic', domain=domain, database=self._validated_database(database),
            display_limit=limit, export_columns=_DOMAIN_ORGANIC_EXPORT_COLUMNS,
        )
