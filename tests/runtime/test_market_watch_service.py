from __future__ import annotations

from runtime.audit_log import RuntimeAuditLog
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.market.market_watch_service import MarketWatchService
from runtime.market.trend_signal import TrendSignal
from runtime.runtime_observability import RuntimeObservability


def test_market_watch_builds_snapshot() -> None:
    service = MarketWatchService(
        trend_engine=MarketTrendEngine(),
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    snapshot = service.inspect(
        (
            TrendSignal("ads", "seg_a", 0.30, 0.20, 0.10, 0.15, 0.40),
            TrendSignal("crm", "seg_a", 0.20, 0.10, 0.00, 0.00, 0.30),
            TrendSignal("ads", "seg_b", -0.10, -0.05, 0.20, 0.15, 0.60),
        )
    )
    assert snapshot.global_macro_score >= 0.0
    assert len(snapshot.segment_states) == 2



def test_market_watch_reports_unattached_managed_runtime_snapshot() -> None:
    service = MarketWatchService(
        trend_engine=MarketTrendEngine(),
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    snapshot = service.managed_runtime_snapshot()
    assert snapshot['attached'] is False
