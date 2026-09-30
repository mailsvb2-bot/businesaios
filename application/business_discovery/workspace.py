from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from application.business_constraint import BusinessConstraintRegistry
from application.business_discovery.contracts import DISCOVERY_FIELDS, DiscoveryFieldSpec
from application.business_discovery.owner_assertion_ingress import (
    OwnerAssertionIngressResult,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from application.business_discovery.provider_observation_ingress import (
    ProviderBusinessObservationIngress,
    ProviderObservationIngressResult,
)
from application.business_goal import BusinessGoalRegistry
from runtime.state import StateSynthesisEngine
from runtime.state.state_contract import StateFieldRecord, StateSynthesizedSnapshot

CANON_BUSINESS_DISCOVERY_WORKSPACE = True
_NON_COVERING_VALUE_KINDS = frozenset({"absent", "stale"})


@dataclass(frozen=True)
class BusinessDiscoveryProgress:
    total_fields: int
    covered_fields: int
    owner_asserted_fields: int
    remaining_fields: int
    complete: bool
    next_field_key: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_fields": self.total_fields,
            "covered_fields": self.covered_fields,
            "owner_asserted_fields": self.owner_asserted_fields,
            "remaining_fields": self.remaining_fields,
            "complete": self.complete,
            "next_field_key": self.next_field_key,
        }


class BusinessDiscoveryWorkspace:
    """Authenticated workspace projection over canonical discovery owners.

    This class does not own persistence. Writes delegate to
    OwnerBusinessAssertionIngress; reads come from the canonical state snapshot
    store already owned by runtime.state.
    """

    def __init__(
        self,
        *,
        ingress: OwnerBusinessAssertionIngress,
        state_engine: StateSynthesisEngine,
        goal_registry: BusinessGoalRegistry | None = None,
        constraint_registry: BusinessConstraintRegistry | None = None,
        provider_observation_ingress: ProviderBusinessObservationIngress | None = None,
    ) -> None:
        if state_engine.snapshot_store is None:
            raise ValueError("canonical durable StateSnapshotStore is required")
        self._ingress = ingress
        self._state = state_engine
        self._goals = goal_registry
        self._constraints = constraint_registry
        self._provider_observations = provider_observation_ingress

    def describe(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, "tenant_id")
        business = _required(business_id, "business_id")
        snapshot = self._state.snapshot_store.load_latest(
            tenant_id=tenant,
            business_id=business,
        )
        fields = tuple(
            self._field_view(spec=spec, snapshot=snapshot)
            for spec in DISCOVERY_FIELDS.values()
        )
        progress = _progress(fields)
        return {
            "tenant_id": tenant,
            "business_id": business,
            "state_id": None if snapshot is None else snapshot.state_id,
            "schema_version": "business_discovery_workspace@v1",
            "fields": list(fields),
            "progress": progress.to_dict(),
        }

    def assert_owner(
        self,
        *,
        assertion: OwnerBusinessAssertion,
        idempotency_key: str,
        recorded_at_ms: int | None = None,
    ) -> dict[str, Any]:
        result = self._ingress.ingest(
            assertion=assertion,
            idempotency_key=idempotency_key,
            recorded_at_ms=recorded_at_ms,
        )
        view = self.describe(
            tenant_id=assertion.tenant_id,
            business_id=assertion.business_id,
        )
        view["assertion"] = _result_payload(result)
        return view

    def reconcile_provider_evidence(
        self,
        *,
        tenant_id: str,
        business_id: str,
        evidence_id: str,
    ) -> dict[str, Any]:
        if self._provider_observations is None:
            raise RuntimeError("canonical provider observation ingress is not configured")
        result = self._provider_observations.reconcile(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            evidence_id=_required(evidence_id, "evidence_id"),
        )
        view = self.describe(tenant_id=tenant_id, business_id=business_id)
        view["provider_reconciliation"] = _provider_result_payload(result)
        return view

    def list_goals(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        if self._goals is None:
            raise RuntimeError("canonical BusinessGoalRegistry is not configured")
        return [
            _jsonable_dataclass(item)
            for item in self._goals.list_for_business(
                tenant_id=_required(tenant_id, "tenant_id"),
                business_id=_required(business_id, "business_id"),
            )
        ]

    def create_goal(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str,
        idempotency_key: str,
        confirmed: bool,
        goal_id: str,
        goal_kind: str,
        target_key: str | None = None,
        metric: str | None = None,
        baseline: float | None = None,
        target: float | None = None,
        deadline_at_ms: int | None = None,
        constraint_ids: tuple[str, ...] = (),
        parent_goal_id: str | None = None,
        priority: int = 50,
        occurred_at_ms: int | None = None,
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError("explicit owner confirmation is required for canonical goal creation")
        if self._goals is None:
            raise RuntimeError("canonical BusinessGoalRegistry is not configured")
        actor = _required(actor_id, "actor_id")
        goal = self._goals.create(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            goal_id=_required(goal_id, "goal_id"),
            idempotency_key=_required(idempotency_key, "idempotency_key"),
            goal_kind=_required(goal_kind, "goal_kind"),
            target_key=target_key,
            metric=metric,
            baseline=baseline,
            target=target,
            deadline_at_ms=deadline_at_ms,
            owner_id=actor,
            constraint_ids=constraint_ids,
            parent_goal_id=parent_goal_id,
            priority=priority,
            occurred_at_ms=occurred_at_ms,
            event_metadata={
                "actor_id": actor,
                "provenance": {
                    "ingress": "business_discovery",
                    "owner_confirmed": True,
                },
            },
        )
        return _jsonable_dataclass(goal)

    def list_constraints(
        self,
        *,
        tenant_id: str,
        business_id: str,
    ) -> list[dict[str, Any]]:
        if self._constraints is None:
            raise RuntimeError("canonical BusinessConstraintRegistry is not configured")
        return [
            _jsonable_dataclass(item)
            for item in self._constraints.list_for_business(
                tenant_id=_required(tenant_id, "tenant_id"),
                business_id=_required(business_id, "business_id"),
            )
        ]

    def create_constraint(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str,
        idempotency_key: str,
        confirmed: bool,
        constraint_id: str,
        constraint_kind: str,
        severity: str = "hard",
        subject_type: str | None = None,
        subject_id: str | None = None,
        state_key: str | None = None,
        comparison: str | None = None,
        threshold: float | None = None,
        occurred_at_ms: int | None = None,
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError(
                "explicit owner confirmation is required for canonical constraint creation"
            )
        if self._constraints is None:
            raise RuntimeError("canonical BusinessConstraintRegistry is not configured")
        actor = _required(actor_id, "actor_id")
        constraint = self._constraints.create(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            constraint_id=_required(constraint_id, "constraint_id"),
            idempotency_key=_required(idempotency_key, "idempotency_key"),
            constraint_kind=_required(constraint_kind, "constraint_kind"),
            severity=severity,
            subject_type=subject_type,
            subject_id=subject_id,
            state_key=state_key,
            comparison=comparison,
            threshold=threshold,
            occurred_at_ms=occurred_at_ms,
            event_metadata={
                "actor_id": actor,
                "provenance": {
                    "ingress": "business_discovery",
                    "owner_confirmed": True,
                },
            },
        )
        return _jsonable_dataclass(constraint)

    @staticmethod
    def _field_view(
        *,
        spec: DiscoveryFieldSpec,
        snapshot: StateSynthesizedSnapshot | None,
    ) -> dict[str, Any]:
        record = None if snapshot is None else snapshot.fields.get(spec.field_path)
        owner_asserted = _is_owner_asserted(record=record, spec=spec)
        covered = _is_covered(record)
        status = _status(record)
        return {
            "key": spec.key,
            "domain": spec.domain,
            "field_path": spec.field_path,
            "value_kind": spec.value_kind.value,
            "allowed_values": list(spec.allowed_values),
            "legacy_sources": list(spec.legacy_sources),
            "status": status,
            "covered": covered,
            "owner_asserted": owner_asserted,
            "provider_observed": _is_provider_observed(record=record, spec=spec),
            "epistemic_status": None if record is None else record.meta.get("epistemic_status"),
            "provider_key": None if record is None else record.meta.get("provider_key"),
            "value": None if record is None else record.value,
            "source": None if record is None else record.source,
            "observed_at_ms": None if record is None else record.observed_at_ms,
            "freshness_status": None if record is None else record.freshness_status,
            "conflict": False if record is None else bool(record.conflict),
            "evidence_ids": (
                []
                if record is None
                else [str(item.evidence_id) for item in record.evidence_refs]
            ),
        }


def _jsonable_dataclass(value: object) -> dict[str, Any]:
    payload = asdict(value)
    return {
        key: (
            item.value
            if hasattr(item, "value") and isinstance(getattr(item, "value"), str)
            else item
        )
        for key, item in payload.items()
    }


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _is_owner_asserted(
    *,
    record: StateFieldRecord | None,
    spec: DiscoveryFieldSpec,
) -> bool:
    if record is None:
        return False
    return (
        str(record.meta.get("business_discovery_field_key") or "") == spec.key
        and str(record.meta.get("epistemic_status") or "") == "OWNER_ASSERTED"
    )


def _is_provider_observed(
    *,
    record: StateFieldRecord | None,
    spec: DiscoveryFieldSpec,
) -> bool:
    if record is None:
        return False
    return (
        str(record.meta.get("business_discovery_field_key") or "") == spec.key
        and str(record.meta.get("observation_role") or "") == "PROVIDER_OBSERVED"
    )


def _is_covered(record: StateFieldRecord | None) -> bool:
    return record is not None and str(record.value_kind) not in _NON_COVERING_VALUE_KINDS


def _status(record: StateFieldRecord | None) -> str:
    if record is None:
        return "missing"
    if bool(record.conflict):
        return "conflict"
    value_kind = str(record.value_kind or "")
    if value_kind == "unknown":
        return "unknown"
    if value_kind in _NON_COVERING_VALUE_KINDS:
        return value_kind
    return "known"


def _progress(fields: tuple[dict[str, Any], ...]) -> BusinessDiscoveryProgress:
    total = len(fields)
    covered = sum(1 for item in fields if bool(item["covered"]))
    owner_asserted = sum(1 for item in fields if bool(item["owner_asserted"]))
    next_key = next(
        (str(item["key"]) for item in fields if not bool(item["covered"])),
        None,
    )
    return BusinessDiscoveryProgress(
        total_fields=total,
        covered_fields=covered,
        owner_asserted_fields=owner_asserted,
        remaining_fields=max(0, total - covered),
        complete=covered == total,
        next_field_key=next_key,
    )


def _provider_result_payload(result: ProviderObservationIngressResult) -> dict[str, Any]:
    return {
        "evidence_id": result.evidence_id,
        "state_id": result.state_id,
        "observed_fields": list(result.observed_fields),
        "verified_fields": list(result.verified_fields),
        "conflicted_fields": list(result.conflicted_fields),
        "replayed": result.replayed,
    }


def _result_payload(result: OwnerAssertionIngressResult) -> dict[str, Any]:
    return {
        "fact_id": result.fact_id,
        "evidence_id": result.evidence_id,
        "state_id": result.state_id,
        "field_path": result.field_path,
        "replayed": result.replayed,
    }


__all__ = [
    "CANON_BUSINESS_DISCOVERY_WORKSPACE",
    "BusinessDiscoveryProgress",
    "BusinessDiscoveryWorkspace",
]
