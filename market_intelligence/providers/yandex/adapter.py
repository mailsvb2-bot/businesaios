from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, UTC
from hashlib import sha256
from math import isfinite

from market_intelligence.contracts import (
    EvidenceRef,
    MarketIntelligenceProvider,
    MarketIntelligenceSnapshot,
    SearchDemandObservation,
    SearchVisibilityObservation,
)
from market_intelligence.providers.yandex.webmaster_client import WebmasterClient
from market_intelligence.providers.yandex.wordstat_client import WordstatClient


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric) or numeric < 0:
        return None
    return int(numeric)


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


class YandexMarketIntelligenceProvider(MarketIntelligenceProvider):
    provider_key = 'yandex'

    def __init__(
        self,
        *,
        wordstat_client: WordstatClient | None = None,
        webmaster_client: WebmasterClient | None = None,
    ) -> None:
        if wordstat_client is None and webmaster_client is None:
            raise ValueError('At least one Yandex market sensor client must be configured')
        self._wordstat = wordstat_client
        self._webmaster = webmaster_client

    @staticmethod
    def _evidence(
        *, source_kind: str, source_id: str, observed_at: datetime, metadata: Mapping[str, object] | None = None
    ) -> EvidenceRef:
        return EvidenceRef(
            provider_key='yandex',
            source_kind=source_kind,
            source_id=sha256(source_id.encode('utf-8')).hexdigest(),
            observed_at=observed_at,
            retrieved_at=observed_at,
            metadata=dict(metadata or {}),
        )

    def keyword_demand(
        self, *, tenant_id: str, business_id: str, queries: Sequence[str], database: str
    ) -> MarketIntelligenceSnapshot:
        now = datetime.now(UTC)
        if self._wordstat is None:
            return MarketIntelligenceSnapshot(
                provider_key=self.provider_key,
                generated_at=now,
                warnings=('wordstat_sensor_not_configured',),
            )
        market = database.strip()
        if not market:
            raise ValueError('database must not be blank')
        by_phrase: dict[str, SearchDemandObservation] = {}
        for root_phrase in queries:
            root_phrase = root_phrase.strip()
            if not root_phrase:
                continue
            for row in self._wordstat.top_requests(phrase=root_phrase):
                phrase = str(row.get('phrase') or '').strip()
                if not phrase:
                    continue
                count = _as_int(row.get('count'))
                candidate = SearchDemandObservation(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    query=phrase,
                    database=market,
                    search_volume=count,
                    cpc=None,
                    competition=None,
                    keyword_difficulty=None,
                    evidence=self._evidence(
                        source_kind='wordstat_top_requests',
                        source_id=f'{market}:{root_phrase}:{phrase}:{now.isoformat()}',
                        observed_at=now,
                        metadata={'root_query': root_phrase},
                    ),
                )
                previous = by_phrase.get(phrase.casefold())
                if previous is None or (candidate.search_volume or -1) > (previous.search_volume or -1):
                    by_phrase[phrase.casefold()] = candidate
        return MarketIntelligenceSnapshot(
            provider_key=self.provider_key,
            generated_at=now,
            demand=tuple(by_phrase[key] for key in sorted(by_phrase)),
        )

    def organic_visibility(
        self, *, tenant_id: str, business_id: str, domain: str, database: str, limit: int = 100
    ) -> MarketIntelligenceSnapshot:
        now = datetime.now(UTC)
        if self._webmaster is None:
            return MarketIntelligenceSnapshot(
                provider_key=self.provider_key,
                generated_at=now,
                warnings=('webmaster_sensor_not_configured',),
            )
        domain = domain.strip()
        market = database.strip()
        if not domain or not market:
            raise ValueError('domain and database must not be blank')
        observations: list[SearchVisibilityObservation] = []
        for row in self._webmaster.popular_queries(limit=limit):
            query = str(row.get('query_text') or '').strip()
            if not query:
                continue
            indicators = row.get('indicators')
            indicators = indicators if isinstance(indicators, Mapping) else {}
            average_position = _as_float(indicators.get('AVG_SHOW_POSITION'))
            observations.append(
                SearchVisibilityObservation(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    domain=domain,
                    query=query,
                    database=market,
                    position=int(round(average_position)) if average_position is not None else None,
                    traffic_percent=None,
                    url=None,
                    evidence=self._evidence(
                        source_kind='webmaster_popular_query',
                        source_id=f'{market}:{domain}:{row.get("query_id") or query}:{now.isoformat()}',
                        observed_at=now,
                        metadata={'average_show_position': average_position},
                    ),
                )
            )
        return MarketIntelligenceSnapshot(
            provider_key=self.provider_key,
            generated_at=now,
            visibility=tuple(observations),
        )
