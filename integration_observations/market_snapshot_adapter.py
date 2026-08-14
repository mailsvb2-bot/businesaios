from __future__ import annotations

from integration_observations.contracts import ProviderObservationEnvelope
from market_intelligence.contracts import MarketIntelligenceSnapshot


def market_snapshot_to_observations(
    snapshot: MarketIntelligenceSnapshot,
) -> tuple[ProviderObservationEnvelope, ...]:
    envelopes: list[ProviderObservationEnvelope] = []
    for item in snapshot.demand:
        envelopes.append(
            ProviderObservationEnvelope(
                tenant_id=item.tenant_id,
                business_id=item.business_id,
                provider_key=snapshot.provider_key,
                observation_type='search.keyword_demand',
                observed_at=item.evidence.observed_at,
                payload={
                    'query': item.query,
                    'database': item.database,
                    'search_volume': item.search_volume,
                    'cpc': item.cpc,
                    'competition': item.competition,
                    'keyword_difficulty': item.keyword_difficulty,
                },
                evidence_ids=(item.evidence.source_id,),
            )
        )
    for item in snapshot.visibility:
        envelopes.append(
            ProviderObservationEnvelope(
                tenant_id=item.tenant_id,
                business_id=item.business_id,
                provider_key=snapshot.provider_key,
                observation_type='search.organic_visibility',
                observed_at=item.evidence.observed_at,
                payload={
                    'domain': item.domain,
                    'query': item.query,
                    'database': item.database,
                    'position': item.position,
                    'traffic_percent': item.traffic_percent,
                    'url': item.url,
                },
                evidence_ids=(item.evidence.source_id,),
            )
        )
    return tuple(envelopes)
