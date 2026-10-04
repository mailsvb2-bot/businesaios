from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, replace
from threading import RLock
from uuid import uuid4

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
from core.experiments.errors import ExperimentOverlapViolation
from core.experiments.types import (
    ExperimentAssignment,
    ExperimentPlan,
    ExperimentResult,
    MetricDefinition,
    VariantMetricSnapshot,
    VariantSpec,
)
from core.utils.canonical import payload_hash

CANON_EXPERIMENT_EVENT_STORE_REPOSITORY = True
_SOURCE = "core.experiments"
_EXPERIMENT_REPOSITORY_LOCK = RLock()
_OVERLAP_REGISTRY_KEY_PREFIX = "experiment.overlap_registry.v1"
_OVERLAP_RESERVATION_TTL_MS = 60_000
_BLOCKING_OVERLAP_STATUSES = {
    ExperimentStatus.DRAFT,
    ExperimentStatus.ACTIVE,
    ExperimentStatus.PAUSED,
}


def _overlap_token(plan: ExperimentPlan, overlap_key: str) -> str:
    return hashlib.sha256(
        f"{plan.subject_key}\x1f{plan.audience_key}\x1f{overlap_key}".encode("utf-8")
    ).hexdigest()


def _overlap_tokens(plan: ExperimentPlan) -> tuple[str, ...]:
    return tuple(sorted({_overlap_token(plan, str(key)) for key in plan.overlap_keys}))


def _revision_event_id(
    *,
    kind: str,
    tenant_id: str,
    business_id: str,
    entity_id: str,
    revision: int,
) -> str:
    token = hashlib.sha256(
        f"{kind}:{tenant_id}:{business_id}:{entity_id}:{int(revision)}".encode("utf-8")
    ).hexdigest()
    return f"experiment.{kind}:{token}"


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

    def _append(
        self,
        *,
        event_type: str,
        entity_id: str,
        body: dict,
        event_id: str | None = None,
        decision_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        now_ms = int(time.time() * 1000)
        append_event_strict(
            self._event_store,
            tenant_id=self._tenant_id,
            event={
                "event_id": str(event_id or f"{event_type}:{entity_id}:{uuid4().hex}"),
                "tenant_id": self._tenant_id,
                "source": _SOURCE,
                "event_type": event_type,
                "timestamp_ms": now_ms,
                "decision_id": decision_id,
                "correlation_id": correlation_id,
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
    def _overlap_registry_key(self) -> str:
        return f"{_OVERLAP_REGISTRY_KEY_PREFIX}:{self._business_id}"

    def _overlap_registry_io(self):
        getter = getattr(self._event_store, "get_setting", None)
        compare_and_set = getattr(self._event_store, "compare_and_set_setting", None)
        if not callable(getter) or not callable(compare_and_set):
            raise RuntimeError("EXPERIMENT_OVERLAP_CAS_REQUIRED")
        return getter, compare_and_set

    def _read_overlap_registry(self):
        getter, _ = self._overlap_registry_io()
        raw = getter(tenant_id=self._tenant_id, key=self._overlap_registry_key())
        if raw is None:
            return None
        if not isinstance(raw, dict) or int(raw.get("schema_version") or 0) != 1:
            raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CORRUPT")
        if not isinstance(raw.get("claims"), dict):
            raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CORRUPT")
        return raw

    def _reconciled_overlap_claims(
        self,
        raw_registry,
        *,
        existing_plans: list[ExperimentPlan],
        now_ms: int,
    ) -> dict[str, dict[str, object]]:
        claims: dict[str, dict[str, object]] = {}
        known_ids = {plan.experiment_id for plan in existing_plans}
        for plan in existing_plans:
            if plan.status not in _BLOCKING_OVERLAP_STATUSES:
                continue
            for token in _overlap_tokens(plan):
                previous = claims.get(token)
                if previous is not None and previous.get("experiment_id") != plan.experiment_id:
                    raise RuntimeError("EXPERIMENT_OVERLAP_STATE_CONFLICT")
                claims[token] = {
                    "experiment_id": plan.experiment_id,
                    "state": "active",
                    "reserved_at_ms": 0,
                }

        raw_claims = dict((raw_registry or {}).get("claims") or {})
        for token, value in raw_claims.items():
            if not isinstance(value, dict):
                raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CORRUPT")
            experiment_id = str(value.get("experiment_id") or "").strip()
            state = str(value.get("state") or "").strip()
            reserved_at_ms = int(value.get("reserved_at_ms") or 0)
            if not experiment_id or state not in {"pending", "active"} or reserved_at_ms < 0:
                raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CORRUPT")
            if experiment_id in known_ids or state != "pending":
                continue
            if reserved_at_ms > now_ms + _OVERLAP_RESERVATION_TTL_MS:
                raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CORRUPT")
            if now_ms - reserved_at_ms <= _OVERLAP_RESERVATION_TTL_MS:
                claims[str(token)] = {
                    "experiment_id": experiment_id,
                    "state": "pending",
                    "reserved_at_ms": reserved_at_ms,
                }
        return claims

    def _compare_and_set_overlap_registry(self, expected, claims) -> bool:
        _, compare_and_set = self._overlap_registry_io()
        return bool(
            compare_and_set(
                tenant_id=self._tenant_id,
                key=self._overlap_registry_key(),
                expected=expected,
                value={"schema_version": 1, "claims": claims},
            )
        )

    def _reconcile_overlap_registry(self) -> None:
        for _ in range(16):
            raw = self._read_overlap_registry()
            now_ms = int(time.time() * 1000)
            claims = self._reconciled_overlap_claims(
                raw,
                existing_plans=self.list_all(),
                now_ms=now_ms,
            )
            value = {"schema_version": 1, "claims": claims}
            if raw == value or self._compare_and_set_overlap_registry(raw, claims):
                return
        raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CONTENTION")

    def register_with_overlap_guard(self, plan: ExperimentPlan, overlap_guard) -> ExperimentPlan:
        active = replace(plan, status=ExperimentStatus.ACTIVE)
        if not active.overlap_keys:
            with _EXPERIMENT_REPOSITORY_LOCK:
                overlap_guard.ensure_no_overlap(
                    candidate_plan=active,
                    existing_plans=self.list_all(),
                )
                return self.save(active)

        with _EXPERIMENT_REPOSITORY_LOCK:
            candidate_tokens = _overlap_tokens(active)
            for _ in range(16):
                existing_plans = self.list_all()
                overlap_guard.ensure_no_overlap(
                    candidate_plan=active,
                    existing_plans=existing_plans,
                )
                raw = self._read_overlap_registry()
                now_ms = int(time.time() * 1000)
                claims = self._reconciled_overlap_claims(
                    raw,
                    existing_plans=existing_plans,
                    now_ms=now_ms,
                )
                for token in candidate_tokens:
                    claim = claims.get(token)
                    if claim is not None and claim.get("experiment_id") != active.experiment_id:
                        raise ExperimentOverlapViolation(
                            f"experiment overlap detected with {claim.get('experiment_id')}"
                        )
                for token in candidate_tokens:
                    claim = claims.get(token)
                    if claim is None or claim.get("state") != "active":
                        claims[token] = {
                            "experiment_id": active.experiment_id,
                            "state": "pending",
                            "reserved_at_ms": now_ms,
                        }
                if not self._compare_and_set_overlap_registry(raw, claims):
                    continue
                try:
                    persisted = self.save(active)
                except Exception:
                    self._reconcile_overlap_registry()
                    raise
                self._reconcile_overlap_registry()
                return persisted
        raise RuntimeError("EXPERIMENT_OVERLAP_REGISTRY_CONTENTION")

    def _latest(self) -> dict[str, tuple[int, ExperimentPlan]]:
        latest: dict[str, tuple[int, ExperimentPlan]] = {}
        conflicts: set[tuple[str, int]] = set()
        fingerprints: dict[tuple[str, int], str] = {}
        for payload in self._payloads(EXPERIMENT_STATE_CHANGED):
            plan = _plan_from_dict(dict(payload.get("plan") or {}))
            revision = int(payload.get("revision") or 1)
            key = (plan.experiment_id, revision)
            fingerprint = payload_hash(_plan_dict(plan))
            previous = fingerprints.get(key)
            if previous is not None and previous != fingerprint:
                conflicts.add(key)
            fingerprints[key] = fingerprint
            current = latest.get(plan.experiment_id)
            if current is None or revision > current[0]:
                latest[plan.experiment_id] = (revision, plan)
        if conflicts:
            raise RuntimeError("EXPERIMENT_STATE_CONFLICT")
        return latest

    def _revision(self, experiment_id: str, revision: int) -> ExperimentPlan | None:
        found = None
        fingerprint = None
        for payload in self._payloads(EXPERIMENT_STATE_CHANGED):
            plan = _plan_from_dict(dict(payload.get("plan") or {}))
            if plan.experiment_id != str(experiment_id):
                continue
            if int(payload.get("revision") or 1) != int(revision):
                continue
            current_fingerprint = payload_hash(_plan_dict(plan))
            if fingerprint is not None and current_fingerprint != fingerprint:
                raise RuntimeError("EXPERIMENT_STATE_CONFLICT")
            fingerprint = current_fingerprint
            found = plan
        return found

    def save(self, plan: ExperimentPlan) -> ExperimentPlan:
        with _EXPERIMENT_REPOSITORY_LOCK:
            current = self._latest().get(plan.experiment_id)
            if current is not None:
                revision, existing = current
                if existing == plan:
                    return plan
                if replace(plan, status=existing.status) != existing:
                    raise ValueError("experiment plan identity collision")
                next_revision = revision + 1
            else:
                next_revision = 1
            event_id = _revision_event_id(
                kind="state",
                tenant_id=self._tenant_id,
                business_id=self._business_id,
                entity_id=plan.experiment_id,
                revision=next_revision,
            )
            try:
                self._append(
                    event_type=EXPERIMENT_STATE_CHANGED,
                    entity_id=plan.experiment_id,
                    event_id=event_id,
                    body={"revision": next_revision, "plan": _plan_dict(plan)},
                    decision_id=str(plan.metadata.get("decision_id") or "") or None,
                    correlation_id=str(plan.metadata.get("correlation_id") or "") or None,
                )
            except Exception as exc:
                raise ValueError("experiment plan identity collision") from exc
            persisted = self._revision(plan.experiment_id, next_revision)
            if persisted is None:
                raise RuntimeError("EXPERIMENT_STATE_APPEND_NOT_OBSERVED")
            if persisted != plan:
                raise ValueError("experiment plan identity collision")
            return persisted

    def get(self, experiment_id: str) -> ExperimentPlan | None:
        current = self._latest().get(str(experiment_id))
        return None if current is None else current[1]

    def list_all(self):
        return [item[1] for item in self._latest().values()]


class EventStoreAssignmentRepository(_ScopedEventRepository):
    def save(self, assignment: ExperimentAssignment) -> ExperimentAssignment:
        existing = self.find_by_subject(assignment.experiment_id, assignment.subject_id)
        if existing is not None:
            return existing
        token = hashlib.sha256(
            f"{self._tenant_id}:{self._business_id}:{assignment.experiment_id}:{assignment.subject_id}".encode("utf-8")
        ).hexdigest()
        event_id = f"experiment.assignment:{token}"
        try:
            self._append(
                event_type=EXPERIMENT_ASSIGNMENT_RECORDED,
                entity_id=assignment.assignment_id,
                event_id=event_id,
                body={"assignment": asdict(assignment)},
                correlation_id=assignment.correlation_id,
            )
        except Exception:
            winner = self.find_by_subject(assignment.experiment_id, assignment.subject_id)
            if winner is not None:
                return winner
            raise
        winner = self.find_by_subject(assignment.experiment_id, assignment.subject_id)
        return assignment if winner is None else winner

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
    def _records(self, experiment_id: str) -> list[tuple[int, ExperimentResult]]:
        records: dict[int, ExperimentResult] = {}
        fingerprints: dict[int, str] = {}
        for payload in self._payloads(EXPERIMENT_RESULT_RECORDED):
            raw = dict(payload.get("result") or {})
            if str(raw.get("experiment_id") or "") != str(experiment_id):
                continue
            result = _result_from_dict(raw)
            revision = int(payload.get("revision") or 1)
            fingerprint = payload_hash(_result_dict(result))
            previous = fingerprints.get(revision)
            if previous is not None and previous != fingerprint:
                raise RuntimeError("EXPERIMENT_RESULT_CONFLICT")
            fingerprints[revision] = fingerprint
            records[revision] = result
        return sorted(records.items(), key=lambda item: item[0])

    def save(self, result: ExperimentResult) -> ExperimentResult:
        with _EXPERIMENT_REPOSITORY_LOCK:
            records = self._records(result.experiment_id)
            for _, existing in records:
                if existing.result_id == result.result_id:
                    if existing != result:
                        raise ValueError("experiment result identity collision")
                    return existing
            next_revision = records[-1][0] + 1 if records else 1
            event_id = _revision_event_id(
                kind="result",
                tenant_id=self._tenant_id,
                business_id=self._business_id,
                entity_id=result.experiment_id,
                revision=next_revision,
            )
            try:
                self._append(
                    event_type=EXPERIMENT_RESULT_RECORDED,
                    entity_id=result.result_id,
                    event_id=event_id,
                    body={"revision": next_revision, "result": _result_dict(result)},
                )
            except Exception as exc:
                raise ValueError("experiment result revision collision") from exc
            persisted = dict(self._records(result.experiment_id)).get(next_revision)
            if persisted is None:
                raise RuntimeError("EXPERIMENT_RESULT_APPEND_NOT_OBSERVED")
            if persisted != result:
                raise ValueError("experiment result revision collision")
            return persisted

    def list_by_experiment(self, experiment_id: str):
        return [result for _, result in self._records(experiment_id)]

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
