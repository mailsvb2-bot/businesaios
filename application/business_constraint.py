from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.business_constraints import (
    BUSINESS_CONSTRAINT_SCHEMA_VERSION,
    BusinessConstraint,
    BusinessConstraintNotFound,
    ConstraintLifecycleStatus,
    ConstraintSeverity,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

CONSTRAINT_CREATED = "constraint.created"
CONSTRAINT_UPDATED = "constraint.updated"
CONSTRAINT_ARCHIVED = "constraint.archived"
CONSTRAINT_FACT_TYPES = frozenset({CONSTRAINT_CREATED, CONSTRAINT_UPDATED, CONSTRAINT_ARCHIVED})
CANON_BUSINESS_CONSTRAINT_PROJECTOR = True
CANON_BUSINESS_CONSTRAINT_LIFECYCLE_OWNER = True


class BusinessConstraintHistoryInvariantViolation(RuntimeError):
    pass


class BusinessConstraintProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, constraint_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in CONSTRAINT_FACT_TYPES or (constraint_id is not None and entity_id != str(constraint_id)):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                    "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    @staticmethod
    def _assert_schema(payload: dict[str, object]) -> None:
        value = payload.get("schema_version")
        if isinstance(value, bool) or value != BUSINESS_CONSTRAINT_SCHEMA_VERSION:
            raise BusinessConstraintHistoryInvariantViolation("business constraint history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, constraint_id: str) -> BusinessConstraint:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)
        if not facts:
            raise BusinessConstraintNotFound(f"business constraint not found: {constraint_id}")
        created_rows = [row for row in facts if row["fact_type"] == CONSTRAINT_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise BusinessConstraintHistoryInvariantViolation("business constraint history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._assert_schema(payload)
        constraint = BusinessConstraint(
            constraint_id=str(constraint_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            constraint_kind=payload.get("constraint_kind"),
            severity=payload.get("severity", ConstraintSeverity.HARD.value),
            subject_type=payload.get("subject_type"),
            subject_id=payload.get("subject_id"),
            state_key=payload.get("state_key"),
            schema_version=payload.get("schema_version"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if constraint.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED:
                raise BusinessConstraintHistoryInvariantViolation("business constraint history continues after archive")
            when = int(row["event_time_ms"])
            update = dict(row["payload"])
            self._assert_schema(update)
            if row["fact_type"] == CONSTRAINT_UPDATED:
                if update.get("constraint_kind", constraint.constraint_kind) != constraint.constraint_kind:
                    raise BusinessConstraintHistoryInvariantViolation("business constraint kind cannot be rewritten")
                if update.get("subject_type", constraint.subject_type) != constraint.subject_type:
                    raise BusinessConstraintHistoryInvariantViolation("business constraint subject type cannot be rewritten")
                if update.get("subject_id", constraint.subject_id) != constraint.subject_id:
                    raise BusinessConstraintHistoryInvariantViolation("business constraint subject id cannot be rewritten")
                constraint = replace(
                    constraint,
                    severity=update.get("severity", constraint.severity),
                    state_key=update.get("state_key", constraint.state_key),
                    updated_at_ms=max(constraint.updated_at_ms, when),
                )
            elif row["fact_type"] == CONSTRAINT_ARCHIVED:
                constraint = replace(
                    constraint,
                    lifecycle_status=ConstraintLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(constraint.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return constraint

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessConstraint, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, constraint_id=value) for value in ids)


class BusinessConstraintRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = BusinessConstraintProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="business_constraint_fact",
            source="business_constraint_registry",
            id_prefix="business-constraint",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(constraint: BusinessConstraint) -> dict[str, object]:
        return {
            "schema_version": constraint.schema_version,
            "constraint_kind": constraint.constraint_kind,
            "severity": constraint.severity.value,
            "subject_type": constraint.subject_type,
            "subject_id": constraint.subject_id,
            "state_key": constraint.state_key,
        }

    @staticmethod
    def _state_token(constraint: BusinessConstraint) -> str:
        return "|".join(
            (
                constraint.lifecycle_status.value,
                str(constraint.updated_at_ms),
                str(constraint.schema_version),
                constraint.constraint_kind,
                constraint.severity.value,
                constraint.subject_type or "",
                constraint.subject_id or "",
                constraint.state_key or "",
            )
        )

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        constraint_id: str,
        idempotency_key: str,
        constraint_kind: str,
        severity: ConstraintSeverity | str = ConstraintSeverity.HARD,
        subject_type: str | None = None,
        subject_id: str | None = None,
        state_key: str | None = None,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessConstraint:
        when = self._time(occurred_at_ms)
        candidate = BusinessConstraint(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            business_id=business_id,
            constraint_kind=constraint_kind,
            severity=severity,
            subject_type=subject_type,
            subject_id=subject_id,
            state_key=state_key,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("business constraint already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
                operation="create", idempotency_key=idempotency_key, fact_type=CONSTRAINT_CREATED, payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
            operation="create", idempotency_key=idempotency_key, fact_type=CONSTRAINT_CREATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        constraint_id: str,
        idempotency_key: str,
        severity: ConstraintSeverity | str | None = None,
        state_key: str | None = None,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessConstraint:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)
        if current.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED:
            raise ValueError("archived business constraint cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = replace(
            current,
            severity=current.severity if severity is None else ConstraintSeverity(severity),
            state_key=current.state_key if state_key is None else state_key,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        if payload == self._payload(current):
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
                operation="update", idempotency_key=idempotency_key, fact_type=CONSTRAINT_UPDATED,
                payload=payload, event_metadata=event_metadata,
            )
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
            expected_state_token=self._state_token(current), operation="update",
            idempotency_key=idempotency_key, fact_type=CONSTRAINT_UPDATED, payload=payload, occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        constraint_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessConstraint:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)
        if current.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
                operation="archive", idempotency_key=idempotency_key, fact_type=CONSTRAINT_ARCHIVED,
                payload={"schema_version": BUSINESS_CONSTRAINT_SCHEMA_VERSION}, event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=constraint_id,
            expected_state_token=self._state_token(current), operation="archive",
            idempotency_key=idempotency_key, fact_type=CONSTRAINT_ARCHIVED,
            payload={"schema_version": BUSINESS_CONSTRAINT_SCHEMA_VERSION}, occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)

    def get(self, *, tenant_id: str, business_id: str, constraint_id: str) -> BusinessConstraint:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, constraint_id=constraint_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessConstraint, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_BUSINESS_CONSTRAINT_LIFECYCLE_OWNER",
    "CANON_BUSINESS_CONSTRAINT_PROJECTOR",
    "CONSTRAINT_FACT_TYPES",
    "BusinessConstraintHistoryInvariantViolation",
    "BusinessConstraintProjector",
    "BusinessConstraintRegistry",
]
