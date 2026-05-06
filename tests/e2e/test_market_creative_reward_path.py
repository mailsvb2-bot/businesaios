from __future__ import annotations

from core.creative_intelligence.models import CreativeEconomicsInput, CreativeEvidenceBundle
from runtime.audit_log import RuntimeAuditLog
from runtime.creative.creative_intelligence_service import CreativeIntelligenceService
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.market.market_watch_service import MarketWatchService
from runtime.market.trend_signal import TrendSignal
from runtime.runtime_observability import RuntimeObservability


def test_market_creative_reward_path_prefers_real_value_over_vanity() -> None:
    obs = RuntimeObservability(audit_log=RuntimeAuditLog())

    market_watch = MarketWatchService(trend_engine=MarketTrendEngine(), observability=obs)
    market_snapshot = market_watch.inspect(
        (
            TrendSignal("ads", "seg_a", 0.20, 0.18, 0.05, 0.04, 0.20),
        )
    )

    service = CreativeIntelligenceService(observability=obs)
    snapshots = service.inspect_many(
        items=(
            CreativeEconomicsInput(
                creative_id="vanity",
                segment_key="seg_a",
                spend=100.0,
                impressions=10000,
                clicks=800,
                conversions=1,
                revenue=30.0,
                cogs=10.0,
                variable_cost=5.0,
            ),
            CreativeEconomicsInput(
                creative_id="money",
                segment_key="seg_a",
                spend=100.0,
                impressions=5000,
                clicks=120,
                conversions=12,
                revenue=500.0,
                cogs=100.0,
                variable_cost=30.0,
            ),
        ),
        evidence_map={},
        market_snapshot=market_snapshot,
    )

    assert snapshots[0].creative_id == "money"
