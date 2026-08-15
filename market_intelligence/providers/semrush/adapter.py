from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256

from market_intelligence.contracts import (
    EvidenceRef,
    MarketIntelligenceProvider,
    MarketIntelligenceSnapshot,
    SearchDemandObservation,
    SearchVisibilityObservation,
)
from market_intelligence.providers.semrush.client import SemrushClient
from market_intelligence.providers.semrush.parser import to_float, to_int


class SemrushMarketIntelligenceProvider(MarketIntelligenceProvider):
    provider_key = 'semrush'
    _V3_KEYWORD_DEPRECATION_WARNING = 'semrush_v3_keyword_reports_deprecated_migrate_to_v4'

    def __init__(self, client: SemrushClient) -> None:
        self._client = client

    @staticmethod
    def _evidence(*, source_kind: str, source_id: str, observed_at: datetime) -> EvidenceRef:
        return EvidenceRef(
            provider_key='semrush', source_kind=source_kind,
            source_id=sha256(source_id.encode('utf-8')).hexdigest(),
            observed_at=observed_at, retrieved_at=observed_at,
        )

    def keyword_demand(self, *, tenant_id: str, business_id: str, queries: Sequence[str], database: str) -> MarketIntelligenceSnapshot:
        now = datetime.now(UTC)
        observations: list[SearchDemandObservation] = []
        rows = self._client.keyword_overviews(phrases=queries, database=database)
        for row in rows:
            phrase = row.get('Keyword') or row.get('Ph') or ''
            observations.append(SearchDemandObservation(
                tenant_id=tenant_id, business_id=business_id, query=phrase,
                database=database, search_volume=to_int(row.get('Search Volume') or row.get('Nq')),
                cpc=to_float(row.get('CPC') or row.get('Cp')),
                competition=to_float(row.get('Competition') or row.get('Co')),
                keyword_difficulty=to_float(
                    row.get('Keyword Difficulty Index')
                    or row.get('Keyword Difficulty')
                    or row.get('Kd')
                ),
                evidence=self._evidence(source_kind='keyword_overview', source_id=f'{database}:{phrase}:{now.isoformat()}', observed_at=now),
            ))
        return MarketIntelligenceSnapshot(
            provider_key=self.provider_key,
            generated_at=now,
            demand=tuple(observations),
            warnings=(self._V3_KEYWORD_DEPRECATION_WARNING,),
        )

    def organic_visibility(self, *, tenant_id: str, business_id: str, domain: str, database: str, limit: int = 100) -> MarketIntelligenceSnapshot:
        now = datetime.now(UTC)
        observations: list[SearchVisibilityObservation] = []
        for row in self._client.domain_organic_keywords(domain=domain, database=database, limit=limit):
            query = row.get('Keyword') or row.get('Ph') or ''
            observations.append(SearchVisibilityObservation(
                tenant_id=tenant_id, business_id=business_id, domain=domain, query=query,
                database=database, position=to_int(row.get('Position') or row.get('Po')),
                traffic_percent=to_float(row.get('Traffic (%)') or row.get('Tr')),
                url=row.get('Url') or row.get('Ur') or None,
                evidence=self._evidence(source_kind='domain_organic', source_id=f'{database}:{domain}:{query}:{now.isoformat()}', observed_at=now),
            ))
        return MarketIntelligenceSnapshot(provider_key=self.provider_key, generated_at=now, visibility=tuple(observations))
