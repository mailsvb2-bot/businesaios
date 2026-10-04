from __future__ import annotations

import time
from dataclasses import asdict

from contracts.event_store import append_event_strict, iter_events_strict
from core.events.event_types import (
    EXPERIMENT_ASSIGNMENT_RECORDED,
    EXPERIMENT_RESULT_RECORDED,
    EXPERIMENT_STATE_CHANGED,
)
from core.experiments.enums import (
    ExperimentStatus,
    MetricDirection,
    RiskLevel,
    RolloutDecision,
    VariantRole,
)
from core.experiments.types import (
    ExperimentAssignment,
    ExperimentPlan,
    ExperimentResult,
    MetricDefinition,
    VariantMetricSnapshot,
    VariantSpec,
)

CANON_EXPERIMENT_EVENT_STORE_REPOSITORY = True
_SOURCE = "core.experiments"


class _ScopedEventRepository:
    def __init__(self, event_store, *, tenant_id: str, business_id: str) -> None:
        self._event_store = event_store
        self._tenant_id = str(tenant_id or "").strip()
        self._business_id = str(business_id or "").strip()
        if not self._tenant_id or not self._business_id:
            raise ValueError("experiment repository requires tenant_id and business_id")

    def _events(self, event_type: str):
        return iter_events_strict(
            self._event_store,
            tenant_id=self._tenant_id,
            start_ms=0,
            end_ms=2**63 - 1,
            event_type=event_type,
        )

    def _append(self, *, event_type: str, entity_id: str, body: dict) -> None:
        now_ms = int(time.time() * 1000)
        append_event_strict(
            self._event_store,
            tenant_id=self._tenant_id,
            event={
                "event_id": f"{event_type}:{entity_id}:{now_ms}",
                "tenant_id": self._tenant_id,
                "source": _SOURCE,
                "event_type": event_type,
                "timestamp_ms": now_ms,
                "payload": {
                    "schema_version": 1,
                    "business_id": self._business_id,
                    "occurred_at_ms": now_ms,
                    **body,
                },
            },
        )

    def _payloads(self, event_type: str):
        for event in self._events(event_type):
            payload = dict(event.get("payload") or {})
            if str(payload.get("business_id") or "") == self._business_id:
                yield payload


def _plan_dict(plan: ExperimentPlan) -> dict:
    return {
        "experiment_id": plan.experiment_id,
        "name": plan.name,
        "hypothesis": plan.hypothesis,
        "subject_key": plan.subject_key,
        "audience_key": plan.audience_key,
        "owner": plan.owner,
        "status": plan.status.value,
        "variants": [
            {
                "variant_id": item.variant_id,
                "name": item.name,
                "role": item.role.value,
                "traffic_share": item.traffic_share,
            }
            for item in plan.variants
        ],
        "metrics": [
            {
                "metric_key": item.metric_key,
                "direction": item.direction.value,
                "minimum_detectable_effect": item.minimum_detectable_effect,
                "guardrail": item.guardrail,
            }
            for item in plan.metrics
        ],
        "minimum_sample_size": plan.minimum_sample_size,
        "duration_days": plan.duration_days,
        "overlap_keys": list(plan.overlap_keys),
        "metadata": dict(plan.metadata),
    }


def _plan_from_dict(data: dict) -> ExperimentPlan:
    return ExperimentPlan(
        experiment_id=str(data["experiment_id"]),
        name=str(data["name"]),
        hypothesis=str(data["hypothesis"]),
        subject_key=str(data["subject_key"]),
        audience_key=str(data["audience_key"]),
        owner=str(data["owner"]),
        status=ExperimentStatus(str(data["status"])),
        variants=[
            VariantSpec(
                variant_id=str(item["variant_id"]),
                name=str(item["name"]),
                role=VariantRole(str(item["role"])),
                traffic_share=float(item["traffic_share"]),
            )
            for item in data.get("variants", [])
        ],
        metrics=[
            MetricDefinition(
                metric_key=str(item["metric_key"]),
                direction=MetricDirection(str(item["direction"])),
                minimum_detectable_effect=float(item["minimum_detectable_effect"]),
                guardrail=bool(item["guardrail"]),
            )
            for item in data.get("metrics", [])
        ],
        minimum_sample_size=int(data["minimum_sample_size"]),
        duration_days=int(data.get("duration_days") or 14),
        overlap_keys=[str(item) for item in data.get("overlap_keys", [])],
        metadata={str(key): str(value) for key, value in dict(data.get("metadata") or {}).items()},
    )


class EventStoreExperimentRepository(_ScopedEventRepository):
    def save(self, plan: ExperimentPlan) -> ExperimentPlan:
        if self.get(plan.experiment_id) == plan:
            return plan
        self._append(
            event_type=EXPERIMENT_STATE_CHANGED,
            entity_id=plan.experiment_id,
            body={"plan": _plan_dict(plan)},
        )
        return plan

    def get(self, experiment_id: str) -> ExperimentPlan | None:
        found = None
        for payload in self._payloads(EXPERIMENT_STATE_CHANGED):
            plan = _plan_from_dict(dict(payload.get("plan") or {}))
            if plan.experiment_id == str(experiment_id):
                found = plan
        return found

    def list_all(self):
        latest: dict[str, ExperimentPlan] = {}
        for payload in self._payloads(EXPERIMENT_STATE_CHANGED):
            plan = _plan_from_dict(dict(payload.get("plan") or {}))
            latest[plan.experiment_id] = plan
        return list(latest.values())


class EventStoreAssignmentRepository(_ScopedEventRepository):
    def save(self, assignment: ExperimentAssignment) -> ExperimentAssignment:
        existing = self.find_by_subject(assignment.experiment_id, assignment.subject_id)
        if existing is not None:
            if existing != assignment:
                raise ValueError("experiment subject assignment is immutable")
            return existing
        self._append(
            event_type=EXPERIMENT_ASSIGNMENT_RECORDED,
            entity_id=assignment.assignment_id,
            body={"assignment": asdict(assignment)},
        )
        return assignment

    def list_by_experiment(self, experiment_id: str):
        return [
            ExperimentAssignment(**dict(payload["assignment"]))
            for payload in self._payloads(EXPERIMENT_ASSIGNMENT_RECORDED)
            if str(dict(payload.get("assignment") or {}).get("experiment_id") or "") == str(experiment_id)
        ]

    def find_by_subject(self, experiment_id: str, subject_id: str) -> ExperimentAssignment | None:
        for assignment in self.list_by_experiment(experiment_id):
            if assignment.subject_id == str(subject_id):
                return assignment
        return None


def _snapshot(data: dict) -> VariantMetricSnapshot:
    return VariantMetricSnapshot(
        variant_id=str(data["variant_id"]),
        exposures=int(data["exposures"]),
        conversions=int(data["conversions"]),
        value=float(data.get("value") or 0.0),
    )


def _result_from_dict(data: dict) -> ExperimentResult:
    return ExperimentResult(
        result_id=str(data["result_id"]),
        experiment_id=str(data["experiment_id"]),
        primary_metric_key=str(data["primary_metric_key"]),
        control_variant_id=str(data["control_variant_id"]),
        treatment_variant_id=str(data["treatment_variant_id"]),
        control=_snapshot(dict(data["control"])),
        treatment=_snapshot(dict(data["treatment"])),
        uplift=float(data["uplift"]),
        p_value=float(data["p_value"]),
        significant=bool(data["significant"]),
        risk_level=RiskLevel(str(data["risk_level"])),
        rollout_decision=RolloutDecision(str(data["rollout_decision"])),
        notes=[str(item) for item in data.get("notes", [])],
    )


def _result_dict(result: ExperimentResult) -> dict:
    data = asdict(result)
    data["risk_level"] = result.risk_level.value
    data["rollout_decision"] = result.rollout_decision.value
    return data


class EventStoreResultRepository(_ScopedEventRepository):
    def save(self, result: ExperimentResult) -> ExperimentResult:
        for existing in self.list_by_experiment(result.experiment_id):
            if existing.result_id == result.result_id:
                if existing != result:
                    raise ValueError("experiment result identity collision")
                return existing
        self._append(
            event_type=EXPERIMENT_RESULT_RECORDED,
            entity_id=result.result_id,
            body={"result": _result_dict(result)},
        )
        return result

    def list_by_experiment(self, experiment_id: str):
        return [
            _result_from_dict(dict(payload["result"]))
            for payload in self._payloads(EXPERIMENT_RESULT_RECORDED)
            if str(dict(payload.get("result") or {}).get("experiment_id") or "") == str(experiment_id)
        ]

    def get_latest(self, experiment_id: str) -> ExperimentResult | None:
        items = self.list_by_experiment(experiment_id)
        return items[-1] if items else None

    def get_latest_by_metric(self, experiment_id: str, primary_metric_key: str) -> ExperimentResult | None:
        for item in reversed(self.list_by_experiment(experiment_id)):
            if item.primary_metric_key == str(primary_metric_key):
                return item
        return None


__all__ = [
    "CANON_EXPERIMENT_EVENT_STORE_REPOSITORY",
    "EventStoreAssignmentRepository",
    "EventStoreExperimentRepository",
    "EventStoreResultRepository",
]
