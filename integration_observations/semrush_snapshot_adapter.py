from __future__ import annotations

from integration_observations.contracts import ProviderObservationEnvelope
from integration_observations.market_snapshot_adapter import market_snapshot_to_observations
from market_intelligence.contracts import MarketIntelligenceSnapshot


def semrush_snapshot_to_observations(
    snapshot: MarketIntelligenceSnapshot,
) -> tuple[ProviderObservationEnvelope, ...]:
    """Compatibility wrapper for the historical provider-specific import."""
    return market_snapshot_to_observations(snapshot)
