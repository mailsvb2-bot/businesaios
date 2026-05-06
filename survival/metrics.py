from __future__ import annotations

from dataclasses import dataclass

from survival.controller import MetricsProvider, SurvivalMetrics


@dataclass(frozen=True)
class StaticSurvivalMetricsProvider(MetricsProvider):
    """Safe default metrics provider for wiring/demo.

    In production, replace with a provider reading from real telemetry.
    """

    cashflow: float = 0.1
    churn_rate: float = 0.05
    error_rate: float = 0.0
    runtime_alive: bool = True
    policy_health: float = 1.0

    def get_metrics(self) -> SurvivalMetrics:
        return SurvivalMetrics(
            cashflow=float(self.cashflow),
            churn_rate=float(self.churn_rate),
            error_rate=float(self.error_rate),
            runtime_alive=bool(self.runtime_alive),
            policy_health=float(self.policy_health),
        )
