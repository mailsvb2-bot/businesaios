from __future__ import annotations

from decimal import Decimal

CANON_OBSERVABILITY_FINANCE_ALIAS_NAMESPACE = True
CANON_OBSERVABILITY_FINANCE_PACKAGE_OWNER = True

def allocation_trace(trace_id: str, allocation_size: int, *, source_snapshot_id: str | None = None) -> dict[str, str | int | None]:
    return {
        "trace_type": "strategic_finance.allocation",
        "trace_id": trace_id,
        "allocation_size": int(allocation_size),
        "source_snapshot_id": source_snapshot_id,
    }

class FinanceMetricsRegistry:
    def __init__(self) -> None:
        self._metrics: dict[str, Decimal] = {}

    def record(self, name: str, value: Decimal) -> None:
        self._metrics[str(name)] = Decimal(str(value))

    def snapshot(self) -> dict[str, Decimal]:
        return dict(self._metrics)

def finance_metrics_registry() -> tuple[str, ...]:
    return (
        "budget_allocation",
        "forecast_error",
        "risk_signal",
        "scenario_decision",
    )

def forecast_trace(trace_id: str, forecast_version: str, *, source_snapshot_id: str | None = None) -> dict[str, str | None]:
    return {
        "trace_type": "strategic_finance.forecast",
        "trace_id": trace_id,
        "forecast_version": forecast_version,
        "source_snapshot_id": source_snapshot_id,
    }

def risk_signal_trace(trace_id: str, risk_code: str, *, source_snapshot_id: str | None = None) -> dict[str, str | None]:
    return {
        "trace_type": "strategic_finance.risk",
        "trace_id": trace_id,
        "risk_code": risk_code,
        "source_snapshot_id": source_snapshot_id,
    }

def scenario_trace(trace_id: str, scenario_name: str, *, source_snapshot_id: str | None = None) -> dict[str, str | None]:
    return {
        "trace_type": "strategic_finance.scenario",
        "trace_id": trace_id,
        "scenario_name": scenario_name,
        "source_snapshot_id": source_snapshot_id,
    }

__all__ = [
    "CANON_OBSERVABILITY_FINANCE_ALIAS_NAMESPACE",
    "CANON_OBSERVABILITY_FINANCE_PACKAGE_OWNER",
    "allocation_trace",
    "FinanceMetricsRegistry",
    "finance_metrics_registry",
    "forecast_trace",
    "risk_signal_trace",
    "scenario_trace",
]
