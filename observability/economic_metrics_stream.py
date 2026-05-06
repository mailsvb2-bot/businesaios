from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


CANON_ECONOMIC_METRICS_STREAM = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: object) -> str:
    return str(value or "").strip()


def _metric_key(name: str, **tags: object) -> str:
    if not tags:
        return name
    normalized = ",".join(f"{key}={_text(val) or 'unknown'}" for key, val in sorted(tags.items()))
    return f"{name}|{normalized}"


class EconomicMetricsSink(Protocol):
    def observe(self, name: str, value: float = 1.0, **tags: object) -> None: ...
    def record_budget_guard(self, result: Mapping[str, Any] | None) -> None: ...
    def record_revenue_verification(self, result: Mapping[str, Any] | None) -> None: ...
    def snapshot(self) -> dict[str, float]: ...


class NoOpEconomicMetricsStream:
    def observe(self, name: str, value: float = 1.0, **tags: object) -> None:
        return None

    def record_budget_guard(self, result: Mapping[str, Any] | None) -> None:
        return None

    def record_revenue_verification(self, result: Mapping[str, Any] | None) -> None:
        return None

    def snapshot(self) -> dict[str, float]:
        return {}


@dataclass
class EconomicMetricsStream:
    counters: dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0, **tags: object) -> None:
        key = _metric_key(name, **tags)
        self.counters[key] = self.counters.get(key, 0.0) + float(value)

    def record_budget_guard(self, result: Mapping[str, Any] | None) -> None:
        payload = _safe_dict(result)
        metadata = _safe_dict(payload.get("metadata"))
        signals = _safe_dict(metadata.get("planning_signals"))
        channel = _text(signals.get("channel") or metadata.get("channel") or "default")
        survival_mode = _text(signals.get("survival_mode") or "normal")

        self.observe("economic.budget_guard.total", 1.0, channel=channel, survival_mode=survival_mode)
        self.observe(
            "economic.budget_guard.allowed",
            1.0 if _safe_bool(payload.get("allowed")) else 0.0,
            channel=channel,
            survival_mode=survival_mode,
        )
        self.observe(
            "economic.budget_guard.operator_required",
            1.0 if _safe_bool(payload.get("operator_required")) else 0.0,
            channel=channel,
            survival_mode=survival_mode,
        )

    def record_revenue_verification(self, result: Mapping[str, Any] | None) -> None:
        payload = _safe_dict(result)
        outcome_kind = _text(payload.get("outcome_kind") or "none")

        self.observe("economic.revenue_verification.total", 1.0, outcome_kind=outcome_kind)
        self.observe(
            "economic.revenue_verification.verified",
            1.0 if _safe_bool(payload.get("verified")) else 0.0,
            outcome_kind=outcome_kind,
        )
        self.observe(
            "economic.revenue.amount",
            _safe_float(payload.get("revenue_amount")),
            outcome_kind=outcome_kind,
        )

    def snapshot(self) -> dict[str, float]:
        return dict(self.counters)


__all__ = [
    "CANON_ECONOMIC_METRICS_STREAM",
    "EconomicMetricsSink",
    "NoOpEconomicMetricsStream",
    "EconomicMetricsStream",
]
