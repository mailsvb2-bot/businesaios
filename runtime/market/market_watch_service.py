from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.market.market_snapshot import MarketSnapshot
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.market.trend_signal import TrendSignal
from runtime.runtime_observability import RuntimeObservability


@dataclass
class MarketWatchService:
    trend_engine: MarketTrendEngine
    observability: RuntimeObservability
    managed_runtime: Any | None = None

    def inspect(self, signals: tuple[TrendSignal, ...]) -> MarketSnapshot:
        for item in signals:
            self.observability.record_model_signal(
                model_name="market_watch",
                signal_type="trend_signal",
                source=item.source,
            )
        snapshot = self.trend_engine.inspect(signals)
        self.observability.record_model_snapshot(
            model_name="market_watch",
            metric_name="global_macro_score",
            metric_value=snapshot.global_macro_score,
        )
        self.observability.record_model_snapshot(
            model_name="market_watch",
            metric_name="global_micro_score",
            metric_value=snapshot.global_micro_score,
        )
        self.observability.record_model_snapshot(
            model_name="market_watch",
            metric_name="global_competitive_shift",
            metric_value=snapshot.global_competitive_shift,
        )
        return snapshot

    def attach_market_intelligence_runtime(self, runtime: Any) -> None:
        self.managed_runtime = runtime

    def start_managed_runtime(self) -> None:
        if self.managed_runtime is None:
            raise RuntimeError("market-intelligence runtime is not attached")
        self.managed_runtime.start()
        self.observability.record_audit_event("market_intelligence_runtime_started")

    def pulse_managed_runtime_once(self) -> tuple[dict[str, Any], ...]:
        if self.managed_runtime is None:
            raise RuntimeError("market-intelligence runtime is not attached")
        results = self.managed_runtime.pulse_once()
        self.observability.record_audit_event(
            "market_intelligence_runtime_pulsed",
            results_count=len(results),
        )
        return results

    def request_managed_runtime_stop(self, *, reason: str = "market_intelligence_runtime_stop") -> None:
        if self.managed_runtime is None:
            return
        self.managed_runtime.request_stop(reason=reason)
        self.observability.record_audit_event("market_intelligence_runtime_stop_requested", reason=str(reason))

    def join_managed_runtime(self, *, timeout_seconds: float = 10.0) -> Any:
        if self.managed_runtime is None:
            raise RuntimeError("market-intelligence runtime is not attached")
        report = self.managed_runtime.join(timeout_seconds=timeout_seconds)
        self.observability.record_audit_event(
            "market_intelligence_runtime_joined",
            pulses=int(getattr(report, "pulses", 0)),
            executed_results=int(getattr(report, "executed_results", 0)),
        )
        return report

    def managed_runtime_snapshot(self) -> dict[str, Any]:
        if self.managed_runtime is None:
            return {"attached": False}
        return {"attached": True, "runtime": self.managed_runtime.snapshot()}
