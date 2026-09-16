from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.risk import (
    RISK_SCHEMA_VERSION,
    Risk,
    RiskLevel,
    RiskLifecycleStatus,
    RiskNotFound,
)
from reliability.idempotency_contract import IdempotencyStore

RISK_CREATED = "risk.created"
RISK_LEVEL_UPDATED = "risk.level.updated"
RISK_CLOSED = "risk.closed"
RISK_FACT_TYPES = frozenset({RISK_CREATED, RISK_LEVEL_UPDATED, RISK_CLOSED})
CANON_RISK_PROJECTOR = True
CANON_RISK_LIFECYCLE_OWNER = True


class RiskHistoryInvariantViolation(RuntimeError):
    pass


class RiskProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self,
        *,
        tenant_id: str,
        business_id: str,
        risk_id: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(
                tenant_id=str(tenant_id),
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in RISK_FACT_TYPES:
                continue
            if risk_id is not None and entity_id != str(risk_id):
                continue
            if str(event.get("source") or "") != "risk_registry":
                raise RiskHistoryInvariantViolation("risk facts must be written by canonical risk_registry")
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
        rows.sort(
            key=lambda row: (
                row["event_time_ms"],
                row["observed_at_ms"],
                row["append_order"],
                row["fact_id"],
            )
        )
        return rows

    @staticmethod
    def _assert_schema(payload: dict[str, object]) -> None:
        value = payload.get("schema_version")
        if isinstance(value, bool) or value != RISK_SCHEMA_VERSION:
            raise RiskHistoryInvariantViolation("risk history has unsupported schema_version")

    @staticmethod
    def _assert_identity(risk: Risk, payload: dict[str, object]) -> None:
        if str(payload.get("risk_type") or "") != risk.risk_type:
            raise RiskHistoryInvariantViolation("risk type cannot be rewritten")
        if payload.get("subject_kind") != risk.subject_kind:
            raise RiskHistoryInvariantViolation("risk subject kind cannot be rewritten")
        if payload.get("subject_id") != risk.subject_id:
            raise RiskHistoryInvariantViolation("risk subject id cannot be rewritten")

    def get(self, *, tenant_id: str, business_id: str, risk_id: str) -> Risk:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, risk_id=risk_id)
        if not facts:
            raise RiskNotFound(f"risk not found: {risk_id}")
        created_rows = [row for row in facts if row["fact_type"] == RISK_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise RiskHistoryInvariantViolation("risk history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._assert_schema(payload)
        risk = Risk(
            risk_id=str(risk_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            risk_type=str(payload.get("risk_type") or ""),
            level=payload.get("level", RiskLevel.MEDIUM.value),
            subject_kind=payload.get("subject_kind"),
            subject_id=payload.get("subject_id"),
            schema_version=payload.get("schema_version", RISK_SCHEMA_VERSION),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if risk.lifecycle_status is RiskLifecycleStatus.CLOSED:
                raise RiskHistoryInvariantViolation("risk history continues after close")
            update = dict(row["payload"])
            self._assert_schema(update)
            self._assert_identity(risk, update)
            when = int(row["event_time_ms"])
            if row["fact_type"] == RISK_LEVEL_UPDATED:
                risk = replace(
                    risk,
                    level=RiskLevel(update.get("level", risk.level.value)),
                    updated_at_ms=max(risk.updated_at_ms, when),
                )
            elif row["fact_type"] == RISK_CLOSED:
                if RiskLevel(update.get("level", risk.level.value)) is not risk.level:
                    raise RiskHistoryInvariantViolation("risk level cannot change during close")
                risk = replace(
                    risk,
                    lifecycle_status=RiskLifecycleStatus.CLOSED,
                    updated_at_ms=max(risk.updated_at_ms, when),
                    closed_at_ms=max(risk.updated_at_ms, when),
                )
        return risk

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Risk, ...]:
        ids = sorted(
            {
                str(row["entity_id"])
                for row in self._facts(tenant_id=tenant_id, business_id=business_id)
                if row["fact_type"] == RISK_CREATED
            }
        )
        return tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, risk_id=risk_id)
            for risk_id in ids
        )


class RiskRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = RiskProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="risk_fact",
            source="risk_registry",
            id_prefix="risk",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        when = int(time.time() * 1000) if value is None else int(value)
        if when < 0:
            raise ValueError("risk timestamp cannot be negative")
        return when

    @staticmethod
    def _transition_time(current: Risk, value: int | None) -> int:
        when = RiskRegistry._time(value)
        if when < current.updated_at_ms:
            raise ValueError("risk transition timestamp cannot move backwards")
        return when

    @staticmethod
    def _payload(risk: Risk) -> dict[str, object]:
        return {
            "schema_version": risk.schema_version,
            "risk_type": risk.risk_type,
            "level": risk.level.value,
            "subject_kind": risk.subject_kind,
            "subject_id": risk.subject_id,
        }

    @staticmethod
    def _state_token(risk: Risk) -> str:
        return "|".join(
            (
                risk.lifecycle_status.value,
                str(risk.updated_at_ms),
                str(risk.schema_version),
                risk.risk_type,
                risk.level.value,
                risk.subject_kind or "",
                risk.subject_id or "",
            )
        )

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        risk_id: str,
        idempotency_key: str,
        risk_type: str,
        level: RiskLevel | str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Risk:
        when = self._time(occurred_at_ms)
        candidate = Risk(
            risk_id=risk_id,
            tenant_id=tenant_id,
            business_id=business_id,
            risk_type=risk_type,
            level=level,
            subject_kind=subject_kind,
            subject_id=subject_id,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, risk_id=risk_id)
        except LookupError:
            current = None
        if current is not None:
            if (
                current.risk_type != candidate.risk_type
                or current.subject_kind != candidate.subject_kind
                or current.subject_id != candidate.subject_id
            ):
                raise ValueError("risk already exists with different identity metadata")
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=risk_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=RISK_CREATED,
                payload=payload,
            )
            if not repaired:
                raise ValueError("risk already exists; create must replay its original durable mutation")
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=risk_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=RISK_CREATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )

    def update_level(
        self,
        *,
        tenant_id: str,
        business_id: str,
        risk_id: str,
        idempotency_key: str,
        level: RiskLevel | str,
        occurred_at_ms: int | None = None,
    ) -> Risk:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )
        if current.lifecycle_status is RiskLifecycleStatus.CLOSED:
            raise ValueError("closed risk cannot be updated")
        next_level = RiskLevel(level)
        if next_level is current.level:
            return current
        when = self._transition_time(current, occurred_at_ms)
        candidate = replace(current, level=next_level, updated_at_ms=when)
        payload = self._payload(candidate)
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=risk_id,
            expected_state_token=self._state_token(current),
            operation="update_level",
            idempotency_key=idempotency_key,
            fact_type=RISK_LEVEL_UPDATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )

    def close(
        self,
        *,
        tenant_id: str,
        business_id: str,
        risk_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Risk:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )
        if current.lifecycle_status is RiskLifecycleStatus.CLOSED:
            return current
        when = self._transition_time(current, occurred_at_ms)
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=risk_id,
            expected_state_token=self._state_token(current),
            operation="close",
            idempotency_key=idempotency_key,
            fact_type=RISK_CLOSED,
            payload=self._payload(current),
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )

    def get(self, *, tenant_id: str, business_id: str, risk_id: str) -> Risk:
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            risk_id=risk_id,
        )

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Risk, ...]:
        return self._projector.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
        )


__all__ = [
    "CANON_RISK_LIFECYCLE_OWNER",
    "CANON_RISK_PROJECTOR",
    "RISK_FACT_TYPES",
    "RiskHistoryInvariantViolation",
    "RiskProjector",
    "RiskRegistry",
]
