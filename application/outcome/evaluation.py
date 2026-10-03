from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

CANON_PHASE14_EVALUATION_ENGINE = True
CANON_PHASE14_CALIBRATION_ENGINE = True

BUSINESS_EVALUATION_METRICS = (
    "revenue",
    "margin",
    "conversion",
    "retention",
    "goal_completion",
    "cost",
    "latency",
    "complaints",
    "human_override",
    "policy_violations",
    "execution_failures",
)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite(value: object, *, name: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _probability(value: object, *, name: str) -> float | None:
    number = _finite(value, name=name)
    if number is None:
        return None
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool) and value in {0, 1}:
        return bool(value)
    return None


def _first_finite(
    source: Mapping[str, Any],
    names: tuple[str, ...],
) -> tuple[float | None, str | None]:
    for name in names:
        if name not in source:
            continue
        value = _finite(source.get(name), name=name)
        if value is not None:
            return value, name
    return None, None


def _first_boolean(
    source: Mapping[str, Any],
    names: tuple[str, ...],
) -> tuple[bool | None, str | None]:
    for name in names:
        if name not in source:
            continue
        value = _boolean(source.get(name))
        if value is not None:
            return value, name
    return None, None


@dataclass(frozen=True)
class OutcomeEvaluation:
    outcome_id: str
    metrics: Mapping[str, float]
    metric_sources: Mapping[str, str]
    missing_metrics: tuple[str, ...]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outcome_id": self.outcome_id,
            "metrics": dict(self.metrics),
            "metric_sources": dict(self.metric_sources),
            "missing_metrics": list(self.missing_metrics),
        }


@dataclass(frozen=True)
class CalibrationObservation:
    outcome_id: str
    decision_id: str
    action_id: str
    confidence: float
    success: float
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outcome_id": self.outcome_id,
            "decision_id": self.decision_id,
            "action_id": self.action_id,
            "confidence": self.confidence,
            "success": self.success,
        }


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    observed_success_rate: float
    absolute_gap: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "count": self.count,
            "mean_confidence": self.mean_confidence,
            "observed_success_rate": self.observed_success_rate,
            "absolute_gap": self.absolute_gap,
        }


@dataclass(frozen=True)
class CalibrationReport:
    sample_size: int
    mean_confidence: float | None
    observed_success_rate: float | None
    calibration_error: float | None
    brier_score: float | None
    expected_calibration_error: float | None
    bins: tuple[CalibrationBin, ...]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sample_size": self.sample_size,
            "mean_confidence": self.mean_confidence,
            "observed_success_rate": self.observed_success_rate,
            "calibration_error": self.calibration_error,
            "brier_score": self.brier_score,
            "expected_calibration_error": self.expected_calibration_error,
            "bins": [item.to_dict() for item in self.bins],
        }


@dataclass(frozen=True)
class BusinessEvaluationReport:
    outcome_count: int
    metric_means: Mapping[str, float]
    metric_counts: Mapping[str, int]
    metric_coverage: Mapping[str, float]
    outcomes: tuple[OutcomeEvaluation, ...]
    calibration: CalibrationReport
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outcome_count": self.outcome_count,
            "metric_means": dict(self.metric_means),
            "metric_counts": dict(self.metric_counts),
            "metric_coverage": dict(self.metric_coverage),
            "outcomes": [item.to_dict() for item in self.outcomes],
            "calibration": self.calibration.to_dict(),
        }


class EvaluationEngine:
    """Canonical Phase 14 evaluator over persisted BusinessOutcome truth."""

    @staticmethod
    def _record(
        observed: dict[str, float],
        sources: dict[str, str],
        name: str,
        value: float | None,
        source: str | None,
    ) -> None:
        if value is None or source is None:
            return
        observed[name] = float(value)
        sources[name] = source

    def evaluate(self, outcome: Mapping[str, Any]) -> OutcomeEvaluation:
        body = _mapping(outcome)
        outcome_id = str(body.get("outcome_id") or "").strip()
        if not outcome_id:
            raise ValueError("outcome_id is required for evaluation")
        metrics = _mapping(body.get("metrics"))
        observed: dict[str, float] = {}
        sources: dict[str, str] = {}

        revenue = _finite(body.get("revenue_amount"), name="revenue_amount")
        revenue_observed = (
            bool(body.get("revenue_verified"))
            or revenue not in (None, 0.0)
            or bool(metrics.get("revenue_observed"))
            or any(
                str(metrics.get(key) or "").strip()
                for key in ("payment_id", "invoice_id", "order_id")
            )
        )
        if revenue_observed:
            self._record(
                observed,
                sources,
                "revenue",
                revenue,
                "business_outcome.revenue_amount",
            )

        margin, margin_source = _first_finite(
            metrics,
            ("margin", "margin_amount", "net_margin", "gross_margin"),
        )
        self._record(observed, sources, "margin", margin, margin_source)

        conversion_rate, conversion_source = _first_finite(
            metrics,
            ("conversion_rate",),
        )
        if conversion_rate is not None:
            self._record(
                observed,
                sources,
                "conversion",
                conversion_rate,
                conversion_source,
            )
        else:
            converted, converted_source = _first_boolean(metrics, ("converted",))
            conversion_observed = bool(metrics.get("conversion_observed")) or converted is True
            if converted is not None and conversion_observed:
                self._record(
                    observed,
                    sources,
                    "conversion",
                    1.0 if converted else 0.0,
                    converted_source,
                )

        retention_rate, retention_source = _first_finite(
            metrics,
            ("retention_rate",),
        )
        if retention_rate is not None:
            self._record(
                observed,
                sources,
                "retention",
                retention_rate,
                retention_source,
            )
        else:
            retained, retained_source = _first_boolean(
                metrics,
                ("retained", "retention_success"),
            )
            if retained is not None and bool(metrics.get("retention_observed")):
                self._record(
                    observed,
                    sources,
                    "retention",
                    1.0 if retained else 0.0,
                    retained_source,
                )

        completion = _probability(
            body.get("completion_ratio"),
            name="completion_ratio",
        )
        self._record(
            observed,
            sources,
            "goal_completion",
            completion,
            "business_outcome.completion_ratio" if completion is not None else None,
        )

        cost, cost_source = _first_finite(
            metrics,
            ("actual_cost", "cost", "spend"),
        )
        self._record(observed, sources, "cost", cost, cost_source)

        latency, latency_source = _first_finite(
            metrics,
            ("latency_ms", "execution_latency_ms"),
        )
        if latency is None:
            seconds, seconds_source = _first_finite(metrics, ("latency_seconds",))
            if seconds is not None:
                latency = seconds * 1000.0
                latency_source = seconds_source
        self._record(observed, sources, "latency", latency, latency_source)

        complaints, complaints_source = _first_finite(
            metrics,
            ("complaint_count", "complaints"),
        )
        if complaints is None:
            complaint, complaint_source = _first_boolean(metrics, ("complaint",))
            if complaint is not None and bool(metrics.get("complaint_observed")):
                complaints = 1.0 if complaint else 0.0
                complaints_source = complaint_source
        self._record(
            observed,
            sources,
            "complaints",
            complaints,
            complaints_source,
        )

        human_override, human_override_source = _first_boolean(
            metrics,
            ("human_override", "override_applied", "operator_override"),
        )
        if human_override is not None and bool(metrics.get("human_override_observed")):
            self._record(
                observed,
                sources,
                "human_override",
                1.0 if human_override else 0.0,
                human_override_source,
            )

        policy_violations, policy_source = _first_finite(
            metrics,
            ("policy_violation_count", "policy_violations"),
        )
        if policy_violations is None:
            policy_violation, policy_bool_source = _first_boolean(
                metrics,
                ("policy_violation",),
            )
            if policy_violation is not None and bool(
                metrics.get("policy_violation_observed")
            ):
                policy_violations = 1.0 if policy_violation else 0.0
                policy_source = policy_bool_source
        self._record(
            observed,
            sources,
            "policy_violations",
            policy_violations,
            policy_source,
        )

        execution_failures, failure_source = _first_finite(
            metrics,
            ("execution_failure_count", "execution_failures"),
        )
        if execution_failures is None:
            explicit_failure, explicit_source = _first_boolean(
                metrics,
                ("execution_failure",),
            )
            if explicit_failure is not None and bool(
                metrics.get("execution_failure_observed")
            ):
                execution_failures = 1.0 if explicit_failure else 0.0
                failure_source = explicit_source
            elif bool(body.get("attempted")):
                execution_failures = 0.0 if bool(body.get("executed")) else 1.0
                failure_source = "business_outcome.executed"
        self._record(
            observed,
            sources,
            "execution_failures",
            execution_failures,
            failure_source,
        )

        missing = tuple(
            name for name in BUSINESS_EVALUATION_METRICS if name not in observed
        )
        return OutcomeEvaluation(
            outcome_id=outcome_id,
            metrics=observed,
            metric_sources=sources,
            missing_metrics=missing,
        )

    def aggregate(
        self,
        evaluations: Iterable[OutcomeEvaluation],
        *,
        calibration: CalibrationReport,
    ) -> BusinessEvaluationReport:
        unique: dict[str, OutcomeEvaluation] = {}
        for item in evaluations:
            prior = unique.get(item.outcome_id)
            if prior is not None and prior != item:
                raise ValueError(f"conflicting evaluation for {item.outcome_id}")
            unique[item.outcome_id] = item
        ordered = tuple(unique[key] for key in sorted(unique))
        totals = {name: 0.0 for name in BUSINESS_EVALUATION_METRICS}
        counts = {name: 0 for name in BUSINESS_EVALUATION_METRICS}
        for item in ordered:
            for name, value in item.metrics.items():
                if name not in totals:
                    continue
                totals[name] += float(value)
                counts[name] += 1
        means = {
            name: totals[name] / counts[name]
            for name in BUSINESS_EVALUATION_METRICS
            if counts[name]
        }
        total_outcomes = len(ordered)
        coverage = {
            name: counts[name] / total_outcomes if total_outcomes else 0.0
            for name in BUSINESS_EVALUATION_METRICS
        }
        return BusinessEvaluationReport(
            outcome_count=total_outcomes,
            metric_means=means,
            metric_counts=counts,
            metric_coverage=coverage,
            outcomes=ordered,
            calibration=calibration,
        )


class CalibrationEngine:
    """Calibrate pre-action confidence against terminal real-world success."""

    def __init__(self, *, bin_count: int = 10) -> None:
        if isinstance(bin_count, bool) or int(bin_count) <= 0:
            raise ValueError("bin_count must be a positive integer")
        self._bin_count = int(bin_count)

    @staticmethod
    def observation(
        *,
        outcome: Mapping[str, Any],
        action_intent: Mapping[str, Any],
    ) -> CalibrationObservation | None:
        body = _mapping(outcome)
        intent = _mapping(action_intent)
        if (
            not body
            or not intent
            or not bool(body.get("goal_terminal"))
            or not bool(body.get("attempted"))
        ):
            return None
        confidence = _probability(
            intent.get("confidence"),
            name="action_intent.confidence",
        )
        if confidence is None:
            return None

        identity = (
            ("tenant_id", body.get("tenant_id"), intent.get("tenant_id")),
            ("business_id", body.get("business_id"), intent.get("business_id")),
            ("decision_id", body.get("decision_id"), intent.get("decision_id")),
            ("intent_id", body.get("intent_id"), intent.get("intent_id")),
        )
        for name, outcome_value, intent_value in identity:
            if str(outcome_value or "").strip() != str(intent_value or "").strip():
                raise ValueError(
                    f"calibration {name} conflicts with canonical outcome"
                )
        intent_action_id = str(intent.get("action_id") or "").strip()
        outcome_action_id = str(body.get("action_id") or "").strip()
        if intent_action_id and intent_action_id != outcome_action_id:
            raise ValueError("calibration action_id conflicts with canonical outcome")
        intent_action_type = str(
            intent.get("action_type") or intent.get("capability_target") or ""
        ).strip()
        outcome_action_type = str(body.get("action_type") or "").strip()
        if intent_action_type and intent_action_type != outcome_action_type:
            raise ValueError("calibration action_type conflicts with canonical outcome")

        outcome_id = str(body.get("outcome_id") or "").strip()
        decision_id = str(body.get("decision_id") or "").strip()
        if not outcome_id or not decision_id or not outcome_action_id:
            raise ValueError("calibration identity is incomplete")
        return CalibrationObservation(
            outcome_id=outcome_id,
            decision_id=decision_id,
            action_id=outcome_action_id,
            confidence=confidence,
            success=1.0 if bool(body.get("goal_achieved")) else 0.0,
        )

    def evaluate(
        self,
        observations: Iterable[CalibrationObservation],
    ) -> CalibrationReport:
        unique: dict[str, CalibrationObservation] = {}
        for observation in observations:
            prior = unique.get(observation.outcome_id)
            if prior is not None and prior != observation:
                raise ValueError(
                    f"conflicting calibration observation for {observation.outcome_id}"
                )
            unique[observation.outcome_id] = observation
        ordered = tuple(unique[key] for key in sorted(unique))
        if not ordered:
            return CalibrationReport(
                sample_size=0,
                mean_confidence=None,
                observed_success_rate=None,
                calibration_error=None,
                brier_score=None,
                expected_calibration_error=None,
                bins=(),
            )

        count = len(ordered)
        mean_confidence = sum(item.confidence for item in ordered) / count
        success_rate = sum(item.success for item in ordered) / count
        brier_score = (
            sum((item.confidence - item.success) ** 2 for item in ordered) / count
        )

        bins: list[CalibrationBin] = []
        weighted_gap = 0.0
        for index in range(self._bin_count):
            lower = index / self._bin_count
            upper = (index + 1) / self._bin_count
            items = [
                item
                for item in ordered
                if lower <= item.confidence < upper
                or (
                    index == self._bin_count - 1
                    and item.confidence == 1.0
                )
            ]
            if not items:
                continue
            bin_confidence = sum(item.confidence for item in items) / len(items)
            bin_success = sum(item.success for item in items) / len(items)
            absolute_gap = abs(bin_confidence - bin_success)
            weighted_gap += (len(items) / count) * absolute_gap
            bins.append(
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    count=len(items),
                    mean_confidence=bin_confidence,
                    observed_success_rate=bin_success,
                    absolute_gap=absolute_gap,
                )
            )

        return CalibrationReport(
            sample_size=count,
            mean_confidence=mean_confidence,
            observed_success_rate=success_rate,
            calibration_error=mean_confidence - success_rate,
            brier_score=brier_score,
            expected_calibration_error=weighted_gap,
            bins=tuple(bins),
        )


__all__ = [
    "BUSINESS_EVALUATION_METRICS",
    "CANON_PHASE14_CALIBRATION_ENGINE",
    "CANON_PHASE14_EVALUATION_ENGINE",
    "BusinessEvaluationReport",
    "CalibrationBin",
    "CalibrationEngine",
    "CalibrationObservation",
    "CalibrationReport",
    "EvaluationEngine",
    "OutcomeEvaluation",
]
