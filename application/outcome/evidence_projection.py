from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from attribution.catalog import CANONICAL_ATTRIBUTION_CHAIN, CANONICAL_CAUSALITY_LEVELS
from contracts.business_outcome import BusinessOutcomeV1
from contracts.event_store import canonical_business_event_contract
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION = True
CANON_BUSINESS_OUTCOME_EVENT_SPINE_PROJECTION = True
OUTCOME_OBSERVED_EVENT_TYPE = "outcome.observed"
_EVENT_SOURCE = "closed_loop.evidence_projection"


class BusinessOutcomeBodyUnavailable(LookupError):
    """A canonical outcome lineage exists, but its full body is unavailable."""


class BusinessOutcomeProjectionConflict(ValueError):
    """Persisted outcome body conflicts with canonical evidence identity."""


BusinessOutcomeEventProjectionConflict = BusinessOutcomeProjectionConflict


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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

        bins: tuple[CalibrationBin, ...] = ()
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
            bins += (
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    count=len(items),
                    mean_confidence=bin_confidence,
                    observed_success_rate=bin_success,
                    absolute_gap=absolute_gap,
                ),
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


def _event_contract_matches(existing_event: dict[str, Any], expected_event: dict[str, Any]) -> bool:
    """Accept exact Phase 13 events or the exact pre-Phase-13 persisted shape.

    Older outcome.observed rows did not contain the derived outcome taxonomy or
    attribution projection. Replay after upgrade must not rewrite those rows,
    but every pre-existing field must still match the canonical evidence.
    """
    existing = canonical_business_event_contract(existing_event)
    expected = canonical_business_event_contract(expected_event)
    if existing == expected:
        return True

    existing_payload = _mapping(existing.get("payload"))
    if "outcome_taxonomy" in existing_payload or "attribution" in existing_payload:
        return False

    legacy_expected_payload = {**_mapping(expected.get("payload")), "schema_version": 1}
    legacy_expected_payload.pop("outcome_taxonomy", None)
    legacy_expected_payload.pop("attribution", None)
    legacy_expected = {**expected, "schema_version": 1, "payload": legacy_expected_payload}
    return existing == legacy_expected


def _validated_attribution(record: EvidenceRecord, outcome: BusinessOutcomeV1) -> dict[str, Any]:
    attribution = _mapping(record.payload.get("attribution"))
    if not attribution:
        return {}
    if str(attribution.get("kind") or "") != "attribution_result":
        raise BusinessOutcomeProjectionConflict("canonical attribution kind is invalid")
    payload = _mapping(attribution.get("payload"))
    chain = _mapping(payload.get("chain"))
    if str(payload.get("model") or "") != "canonical_lineage_v1":
        raise BusinessOutcomeProjectionConflict("canonical attribution model is invalid")
    if str(payload.get("tenant_id") or "") != record.tenant_id or str(payload.get("business_id") or "") != record.business_id:
        raise BusinessOutcomeProjectionConflict("canonical attribution scope conflicts with evidence")
    missing = [key for key in CANONICAL_ATTRIBUTION_CHAIN if not str(chain.get(key) or "").strip()]
    if list(payload.get("missing_chain") or []) != missing or bool(payload.get("complete_chain")) != (not missing):
        raise BusinessOutcomeProjectionConflict("canonical attribution completeness is inconsistent")
    level = str(payload.get("causality_level") or "")
    if level not in CANONICAL_CAUSALITY_LEVELS:
        raise BusinessOutcomeProjectionConflict("canonical attribution causality level is invalid")
    evidence_refs = tuple(str(item).strip() for item in payload.get("evidence_refs") or () if str(item).strip())
    attribution_proof_refs = tuple(
        str(item).strip() for item in payload.get("attribution_proof_refs") or () if str(item).strip()
    )
    experiment_evidence_refs = tuple(
        str(item).strip() for item in payload.get("experiment_evidence_refs") or () if str(item).strip()
    )
    record_refs = set(record.refs)
    if any(ref not in record_refs for ref in (*evidence_refs, *attribution_proof_refs, *experiment_evidence_refs)):
        raise BusinessOutcomeProjectionConflict("canonical attribution evidence conflicts with evidence record")
    intent = _mapping(record.payload.get("action_intent"))
    intent_schema = int(intent.get("schema_version") or 0)
    parameters = _mapping(intent.get("parameters") if intent_schema == 2 else intent.get("payload"))
    meta = _mapping(parameters.get("meta"))
    metrics = _mapping(outcome.metrics)

    def expected_node(name: str) -> str:
        values = {
            str(source.get(f"{name}_id") or "").strip()
            for source in (metrics, parameters, meta)
            if str(source.get(f"{name}_id") or "").strip()
        }
        if len(values) > 1:
            raise BusinessOutcomeProjectionConflict(
                f"canonical attribution {name} source conflicts with persisted evidence"
            )
        return next(iter(values), "")

    expected = {
        "goal": str(dict(record.labels).get("goal_id") or "").strip(),
        "decision": outcome.decision_id,
        "action": outcome.action_id,
        "interaction": expected_node("interaction"),
        "customer": expected_node("customer"),
        "conversion": expected_node("conversion"),
        "payment": expected_node("payment"),
        "outcome": outcome.outcome_id,
    }
    if any(value and str(chain.get(key) or "") != value for key, value in expected.items()):
        raise BusinessOutcomeProjectionConflict("canonical attribution lineage conflicts with outcome")
    if level != "correlated" and (missing or not bool(payload.get("verified")) or not evidence_refs):
        raise BusinessOutcomeProjectionConflict("canonical attribution overstates causal evidence")
    if level == "strongly_attributed" and (
        not bool(payload.get("attribution_verified")) or not attribution_proof_refs
    ):
        raise BusinessOutcomeProjectionConflict("strong attribution requires explicit attribution proof")
    if level == "experimentally_validated" and (
        not bool(payload.get("experiment_validated"))
        or not str(payload.get("experiment_id") or "").strip()
        or not experiment_evidence_refs
    ):
        raise BusinessOutcomeProjectionConflict("experimental attribution requires experiment evidence")
    return attribution


def _project_record(record: EvidenceRecord) -> BusinessOutcomeV1:
    body = _mapping(record.payload.get("business_outcome"))
    if not body:
        raise BusinessOutcomeBodyUnavailable(f"business outcome body unavailable for {record.lineage.get('outcome', '')}")
    required = ("tenant_id", "business_id", "run_id", "intent_id", "decision_id", "action_id", "action_type", "goal", "status", "outcome_id")
    if any(not str(body.get(name) or "").strip() for name in required):
        raise BusinessOutcomeProjectionConflict("business outcome body is incomplete")
    feedback = {
        "attempted": bool(body.get("attempted")), "executed": bool(body.get("executed")), "verified": bool(body.get("verified")),
        "verification_status": str(body.get("evidence_status") or "unknown"),
        "goal_evaluation": {"achieved": bool(body.get("goal_achieved")), "terminal": bool(body.get("goal_terminal")), "completion_ratio": body.get("completion_ratio"), "success_confidence": body.get("success_confidence")},
        "revenue_outcome": {"revenue_amount": body.get("revenue_amount"), "verified": bool(body.get("revenue_verified"))},
        "normalized_outcome": _mapping(body.get("metrics")), "execution_feedback": {"source_of_truth": str(body.get("source_of_truth") or "feedback_contract")},
        "external_refs": list(body.get("external_refs") or ()), "evidence_status": str(body.get("evidence_status") or "unknown"),
    }
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id=str(body["tenant_id"]), business_id=str(body["business_id"]), run_id=str(body["run_id"]), intent_id=str(body["intent_id"]),
        decision_id=str(body["decision_id"]), action_id=str(body["action_id"]), action_type=str(body["action_type"]), goal=str(body["goal"]),
        status=str(body["status"]), feedback=feedback, evidence_refs=tuple(str(item) for item in body.get("evidence_refs") or ()),
        derived_fact_ref=str(body.get("derived_fact_ref") or ""),
    )
    if int(body.get("schema_version") or 0) != outcome.schema_version or outcome.as_dict() != dict(body):
        raise BusinessOutcomeProjectionConflict("business outcome body conflicts with canonical contract")
    checks = (
        (record.tenant_id, outcome.tenant_id, "tenant"), (record.business_id, outcome.business_id, "business"), (record.run_id, outcome.run_id, "run"),
        (record.action_id or "", outcome.action_id, "action"), (record.lineage.get("outcome", ""), outcome.outcome_id, "outcome"),
        (record.lineage.get("decision", ""), outcome.decision_id, "decision"),
    )
    for actual, expected, label in checks:
        if str(actual or "") != str(expected or ""):
            raise BusinessOutcomeProjectionConflict(f"business outcome {label} identity conflicts with evidence")
    derived = str(record.lineage.get("derived_fact") or "")
    if derived and derived != outcome.derived_fact_ref:
        raise BusinessOutcomeProjectionConflict("business outcome derived fact conflicts with evidence")
    return outcome


class BusinessOutcomeEvidenceProjector:
    """Read-only BusinessOutcomeV1 projection over the canonical EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self._evidence = evidence_store

    @staticmethod
    def _is_outcome_record(record: EvidenceRecord, *, business_id: str) -> bool:
        return record.scope == "closed_loop" and record.source_type == "closed_loop_verification" and record.business_id == str(business_id) and bool(str(record.lineage.get("outcome") or ""))

    def _project_record(self, record: EvidenceRecord) -> BusinessOutcomeV1:
        return _project_record(record)

    def get(self, *, tenant_id: str, business_id: str, outcome_id: str, limit: int = 1000) -> BusinessOutcomeV1:
        target = str(outcome_id or "").strip()
        if not target:
            raise ValueError("outcome_id is required")
        rows = [row for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit) if self._is_outcome_record(row, business_id=business_id) and str(row.lineage.get("outcome") or "") == target and _mapping(row.payload.get("business_outcome"))]
        if not rows:
            raise LookupError(f"business outcome not found: {target}")
        items = tuple(_project_record(row) for row in rows)
        if any(item != items[0] for item in items[1:]):
            raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
        return items[0]

    def list_for_business(self, *, tenant_id: str, business_id: str, limit: int = 1000) -> tuple[BusinessOutcomeV1, ...]:
        projected: dict[str, BusinessOutcomeV1] = {}
        for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit):
            if not self._is_outcome_record(row, business_id=business_id) or not _mapping(row.payload.get("business_outcome")):
                continue
            outcome = _project_record(row)
            if (prior := projected.get(outcome.outcome_id)) is not None and prior != outcome:
                raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
            projected[outcome.outcome_id] = outcome
        return tuple(projected[key] for key in sorted(projected))

    def legacy_incomplete_count(self, *, tenant_id: str, business_id: str, limit: int = 1000) -> int:
        return sum(1 for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit) if self._is_outcome_record(row, business_id=business_id) and not _mapping(row.payload.get("business_outcome")))


class BusinessOutcomeEvaluationProjector:
    """Read-only Phase 14 evaluation/calibration over canonical Outcome evidence."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self._evidence = evidence_store
        self._outcomes = BusinessOutcomeEvidenceProjector(evidence_store)
        self._evaluation = EvaluationEngine()
        self._calibration = CalibrationEngine()

    def evaluate_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        limit: int = 1000,
    ) -> BusinessEvaluationReport:
        outcomes = self._outcomes.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
            limit=limit,
        )
        records_by_outcome: dict[str, tuple[EvidenceRecord, ...]] = {}
        for record in self._evidence.list_for_tenant(
            tenant_id=tenant_id,
            limit=limit,
        ):
            if not BusinessOutcomeEvidenceProjector._is_outcome_record(
                record,
                business_id=business_id,
            ):
                continue
            if not _mapping(record.payload.get("business_outcome")):
                continue
            outcome_id = str(record.lineage.get("outcome") or "").strip()
            records_by_outcome[outcome_id] = (
                *records_by_outcome.get(outcome_id, ()),
                record,
            )

        evaluations: tuple[OutcomeEvaluation, ...] = ()
        observations: tuple[CalibrationObservation, ...] = ()
        for outcome in outcomes:
            records = records_by_outcome.get(outcome.outcome_id, [])
            if not records:
                raise BusinessOutcomeProjectionConflict(
                    "canonical outcome evaluation lost its evidence row"
                )

            evaluation = self._evaluation.evaluate(outcome.as_dict())
            expected_evaluation = evaluation.to_dict()
            for record in records:
                persisted = _mapping(record.payload.get("evaluation"))
                if persisted and persisted != expected_evaluation:
                    raise BusinessOutcomeProjectionConflict(
                        "canonical evaluation conflicts with business outcome"
                    )
            evaluations += (evaluation,)

            intents = [
                _mapping(record.payload.get("action_intent"))
                for record in records
                if _mapping(record.payload.get("action_intent"))
            ]
            action_intent: dict[str, Any] = {}
            if intents:
                action_intent = intents[0]
                if any(item != action_intent for item in intents[1:]):
                    raise BusinessOutcomeProjectionConflict(
                        "canonical calibration action intent is ambiguous"
                    )

            observation = (
                self._calibration.observation(
                    outcome=outcome.as_dict(),
                    action_intent=action_intent,
                )
                if action_intent
                else None
            )
            expected_observation = (
                observation.to_dict() if observation is not None else {}
            )
            for record in records:
                persisted = _mapping(
                    record.payload.get("calibration_observation")
                )
                if persisted and persisted != expected_observation:
                    raise BusinessOutcomeProjectionConflict(
                        "canonical calibration conflicts with business outcome"
                    )
            if observation is not None:
                observations += (observation,)

        calibration = self._calibration.evaluate(observations)
        return self._evaluation.aggregate(
            evaluations,
            calibration=calibration,
        )


class BusinessOutcomeEventSpineProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _matches(self, record: EvidenceRecord, event_id: str) -> list[dict[str, Any]]:
        return [dict(raw) for raw in self._events.iter_events(tenant_id=record.tenant_id, start_ms=0, event_type=OUTCOME_OBSERVED_EVENT_TYPE) if str(raw.get("event_id") or "") == event_id]

    def project(self, record: EvidenceRecord) -> str | None:
        normalized = record.normalized()
        body = _mapping(normalized.payload.get("business_outcome"))
        if not body or body.get("schema_version") is None:
            return None
        outcome = _project_record(normalized)
        intent, correlation_id = _mapping(normalized.payload.get("action_intent")), None
        if intent:
            checks = ((intent.get("tenant_id"), outcome.tenant_id), (intent.get("business_id"), outcome.business_id), (intent.get("decision_id"), outcome.decision_id), (intent.get("intent_id"), outcome.intent_id))
            intent_schema = int(intent.get("schema_version") or 0)
            if intent_schema not in {1, 2} or any(str(a or "") != str(b or "") for a, b in checks):
                raise BusinessOutcomeEventProjectionConflict("action intent identity conflicts with canonical outcome")
            if intent_schema == 2:
                evidence_goal_id = str(dict(normalized.labels).get("goal_id") or "").strip()
                intent_goal_id = str(intent.get("goal_id") or "").strip()
                if evidence_goal_id and evidence_goal_id != intent_goal_id:
                    raise BusinessOutcomeEventProjectionConflict("action intent goal identity conflicts with canonical outcome")
            correlation_id = str(intent.get("correlation_id") or "").strip() or None
        attribution = _validated_attribution(normalized, outcome)
        timestamp_ms, event_id = int(normalized.created_at.timestamp() * 1000), f"closed-loop-outcome:{normalized.evidence_id}"
        event_payload = {
            "schema_version": 2,
            "business_id": normalized.business_id,
            "occurred_at_ms": timestamp_ms,
            "recorded_at_ms": timestamp_ms,
            "causation_id": outcome.intent_id,
            "evidence_ids": [normalized.evidence_id],
            "outcome": outcome.as_dict(),
            "outcome_taxonomy": list(outcome.taxonomy()),
            **({"attribution": attribution} if attribution else {}),
        }
        goal_id = str(dict(normalized.labels).get("goal_id") or "").strip()
        if goal_id:
            event_payload["goal_id"] = goal_id
        event = {
            "event_id": event_id, "tenant_id": normalized.tenant_id, "source": _EVENT_SOURCE, "event_type": OUTCOME_OBSERVED_EVENT_TYPE,
            "timestamp_ms": timestamp_ms, "decision_id": outcome.decision_id, "correlation_id": correlation_id,
            "payload": event_payload,
        }
        matches = self._matches(normalized, event_id)
        if len(matches) > 1:
            raise BusinessOutcomeEventProjectionConflict("multiple Event Spine rows share one outcome projection id")
        if matches:
            if not _event_contract_matches(matches[0], event):
                raise BusinessOutcomeEventProjectionConflict("outcome Event Spine projection conflicts with canonical evidence")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            matches = self._matches(normalized, event_id)
            if not matches or not _event_contract_matches(matches[0], event):
                raise
            return event_id
        matches = self._matches(normalized, event_id)
        if len(matches) != 1:
            raise RuntimeError("outcome Event Spine append did not become durable")
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise BusinessOutcomeEventProjectionConflict("outcome Event Spine projection conflicts with canonical evidence")
        return event_id


__all__ = ["BUSINESS_EVALUATION_METRICS", "CANON_PHASE14_CALIBRATION_ENGINE", "CANON_PHASE14_EVALUATION_ENGINE", "BusinessEvaluationReport", "BusinessOutcomeBodyUnavailable", "BusinessOutcomeEvaluationProjector", "BusinessOutcomeEvidenceProjector", "BusinessOutcomeEventProjectionConflict", "BusinessOutcomeEventSpineProjector", "BusinessOutcomeProjectionConflict", "CalibrationBin", "CalibrationEngine", "CalibrationObservation", "CalibrationReport", "EvaluationEngine", "OutcomeEvaluation", "CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION", "CANON_BUSINESS_OUTCOME_EVENT_SPINE_PROJECTION", "OUTCOME_OBSERVED_EVENT_TYPE"]
