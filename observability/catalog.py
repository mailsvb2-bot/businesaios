from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field

from observability.demand._emitter import emit_event
from observability.metric_counter import MetricCounter


class ExecutionMetrics(MetricCounter):
    def record_execution(self, *, route: str, status: str, duration_ms: float) -> None:
        self.inc(f"execution.route.{route}")
        self.inc(f"execution.status.{status}")
        self.inc("execution.duration_samples", float(duration_ms))

    def snapshot(self) -> dict[str, float]:
        return super().snapshot()


class ExperimentMetrics(MetricCounter):
    def record_assignment(self, *, experiment_id: str, variant_id: str) -> None:
        self.inc(f"experiment.assignment.{experiment_id}.{variant_id}")

    def record_outcome(self, *, experiment_id: str, variant_id: str, value: float = 1.0) -> None:
        self.inc(f"experiment.outcome.{experiment_id}.{variant_id}", float(value))

    def snapshot(self) -> dict[str, float]:
        return super().snapshot()


class LeadMetrics(MetricCounter):
    def record_lead(self, *, source: str, stage: str, value: float = 1.0) -> None:
        self.inc(f"lead.source.{source}", float(value))
        self.inc(f"lead.stage.{stage}", float(value))

    def snapshot(self) -> dict[str, float]:
        return super().snapshot()


@dataclass
class PlatformMetrics:
    values: dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0) -> None:
        self.values[name] = self.values.get(name, 0.0) + value


@dataclass
class MagicMomentEvents:
    values: dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0) -> None:
        self.values[name] = self.values.get(name, 0.0) + value


@dataclass
class RevenueMetrics:
    values: dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0) -> None:
        self.values[name] = self.values.get(name, 0.0) + value


@dataclass
class SeoMetrics:
    values: dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0) -> None:
        self.values[name] = self.values.get(name, 0.0) + value


def emit(event_log: object | None, event_name: str, payload: dict[str, object]) -> None:
    emit_event(
        event_log,
        event_type="growth",
        event_name=event_name,
        payload=dict(payload),
        source="growth",
    )


OBSERVABILITY_COMPAT_EXPORTS = {
    'execution_metrics': {'ExecutionMetrics': 'observability.catalog:ExecutionMetrics'},
    'experiment_metrics': {'ExperimentMetrics': 'observability.catalog:ExperimentMetrics'},
    'lead_metrics': {'LeadMetrics': 'observability.catalog:LeadMetrics'},
    'platform_metrics': {'PlatformMetrics': 'observability.catalog:PlatformMetrics'},
    'magic_moment_events': {'MagicMomentEvents': 'observability.catalog:MagicMomentEvents'},
    'revenue_metrics': {'RevenueMetrics': 'observability.catalog:RevenueMetrics'},
    'seo_metrics': {'SeoMetrics': 'observability.catalog:SeoMetrics'},
    'growth_events': {'emit': 'observability.catalog:emit'},
}

__all__ = (
    'OBSERVABILITY_COMPAT_EXPORTS', 'ExecutionMetrics', 'ExperimentMetrics',
    'LeadMetrics', 'PlatformMetrics', 'MagicMomentEvents', 'RevenueMetrics',
    'SeoMetrics', 'emit',
)
