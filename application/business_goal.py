from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.business_constraint import BusinessConstraintProjector
from application.ontology import EventFactLifecycleWriter
from contracts.business_goal import (
    BUSINESS_GOAL_SCHEMA_VERSION,
    BusinessGoal,
    BusinessGoalNotFound,
    GoalLifecycleStatus,
)
from contracts.business_constraints import BusinessConstraintNotFound, ConstraintLifecycleStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

GOAL_CREATED = "goal.created"
GOAL_UPDATED = "goal.updated"
GOAL_COMPLETED = "goal.completed"
GOAL_CANCELLED = "goal.cancelled"
GOAL_ARCHIVED = "goal.archived"
GOAL_FACT_TYPES = frozenset({GOAL_CREATED, GOAL_UPDATED, GOAL_COMPLETED, GOAL_CANCELLED, GOAL_ARCHIVED})
CANON_BUSINESS_GOAL_PROJECTOR = True
CANON_BUSINESS_GOAL_LIFECYCLE_OWNER = True
_UNSET = object()


class BusinessGoalHistoryInvariantViolation(RuntimeError):
    pass


class BusinessGoalProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store
        self._constraints = BusinessConstraintProjector(event_store)

    def _facts(self, *, tenant_id: str, business_id: str, goal_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in GOAL_FACT_TYPES or (goal_id is not None and entity_id != str(goal_id)):
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
        if isinstance(value, bool) or value != BUSINESS_GOAL_SCHEMA_VERSION:
            raise BusinessGoalHistoryInvariantViolation("business goal history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, goal_id: str) -> BusinessGoal:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)
        if not facts:
            raise BusinessGoalNotFound(f"business goal not found: {goal_id}")
        created_rows = [row for row in facts if row["fact_type"] == GOAL_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise BusinessGoalHistoryInvariantViolation("business goal history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._assert_schema(payload)
        goal = BusinessGoal(
            goal_id=str(goal_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            goal_kind=payload.get("goal_kind"),
            target_key=payload.get("target_key"),
            metric=payload.get("metric"),
            baseline=payload.get("baseline"),
            target=payload.get("target"),
            deadline_at_ms=payload.get("deadline_at_ms"),
            owner_id=payload.get("owner_id"),
            constraint_ids=tuple(payload.get("constraint_ids") or ()),
            parent_goal_id=payload.get("parent_goal_id"),
            priority=payload.get("priority", 50),
            schema_version=payload.get("schema_version"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        terminal_map = {
            GOAL_COMPLETED: GoalLifecycleStatus.COMPLETED,
            GOAL_CANCELLED: GoalLifecycleStatus.CANCELLED,
            GOAL_ARCHIVED: GoalLifecycleStatus.ARCHIVED,
        }
        for row in facts[1:]:
            if goal.lifecycle_status is not GoalLifecycleStatus.ACTIVE:
                raise BusinessGoalHistoryInvariantViolation("business goal history continues after terminal transition")
            when = int(row["event_time_ms"])
            update = dict(row["payload"])
            self._assert_schema(update)
            if row["fact_type"] == GOAL_UPDATED:
                if update.get("goal_kind", goal.goal_kind) != goal.goal_kind:
                    raise BusinessGoalHistoryInvariantViolation("business goal kind cannot be rewritten")
                update_metric = update.get("metric", update.get("target_key", goal.metric))
                if update_metric != goal.metric:
                    raise BusinessGoalHistoryInvariantViolation("business goal metric cannot be rewritten")
                if update.get("parent_goal_id", goal.parent_goal_id) != goal.parent_goal_id:
                    raise BusinessGoalHistoryInvariantViolation("business goal parent cannot be rewritten")
                goal = replace(
                    goal,
                    priority=update.get("priority", goal.priority),
                    baseline=update.get("baseline", goal.baseline),
                    target=update.get("target", goal.target),
                    deadline_at_ms=update.get("deadline_at_ms", goal.deadline_at_ms),
                    owner_id=update.get("owner_id", goal.owner_id),
                    constraint_ids=tuple(update.get("constraint_ids", goal.constraint_ids) or ()),
                    updated_at_ms=max(goal.updated_at_ms, when),
                )
            elif row["fact_type"] in terminal_map:
                goal = replace(
                    goal,
                    lifecycle_status=terminal_map[str(row["fact_type"])],
                    updated_at_ms=max(goal.updated_at_ms, when),
                    terminal_at_ms=when,
                )
        return goal

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessGoal, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, goal_id=value) for value in ids)

    @staticmethod
    def _decision_view(goal: BusinessGoal) -> dict[str, object]:
        return {
            "goal_id": goal.goal_id,
            "goal_kind": goal.goal_kind,
            "metric": goal.metric,
            "baseline": goal.baseline,
            "target": goal.target,
            "deadline_at_ms": goal.deadline_at_ms,
            "priority": goal.priority,
            "owner_id": goal.owner_id,
            "constraint_ids": list(goal.constraint_ids),
            "parent_goal_id": goal.parent_goal_id,
            "lifecycle_status": goal.lifecycle_status.value,
            "updated_at_ms": goal.updated_at_ms,
        }

    @staticmethod
    def _constraint_decision_view(constraint: Any) -> dict[str, object]:
        return {
            "constraint_id": constraint.constraint_id,
            "constraint_kind": constraint.constraint_kind,
            "severity": constraint.severity.value,
            "subject_type": constraint.subject_type,
            "subject_id": constraint.subject_id,
            "state_key": constraint.state_key,
            "lifecycle_status": constraint.lifecycle_status.value,
            "updated_at_ms": constraint.updated_at_ms,
        }

    def load_context(self, *, tenant_id: str, business_id: str, goal_id: str) -> dict[str, object]:
        goals = {
            goal.goal_id: goal
            for goal in self.list_for_business(tenant_id=tenant_id, business_id=business_id)
        }
        try:
            current = goals[str(goal_id)]
        except KeyError as exc:
            raise BusinessGoalNotFound(f"business goal not found: {goal_id}") from exc

        ancestors: list[BusinessGoal] = []
        seen = {current.goal_id}
        cursor = current.parent_goal_id
        while cursor is not None:
            if cursor in seen:
                raise BusinessGoalHistoryInvariantViolation("business goal hierarchy contains a cycle")
            seen.add(cursor)
            parent = goals.get(cursor)
            if parent is None:
                raise BusinessGoalHistoryInvariantViolation(
                    "business goal hierarchy references a missing canonical parent"
                )
            ancestors.append(parent)
            cursor = parent.parent_goal_id
        ancestors.reverse()

        children = sorted(
            (goal for goal in goals.values() if goal.parent_goal_id == current.goal_id),
            key=lambda goal: (-goal.priority, goal.goal_id),
        )
        linked_constraints: list[dict[str, object]] = []
        unresolved_constraint_ids: list[str] = []
        for constraint_id in current.constraint_ids:
            try:
                constraint = self._constraints.get(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    constraint_id=constraint_id,
                )
            except BusinessConstraintNotFound:
                unresolved_constraint_ids.append(constraint_id)
                continue
            linked_constraints.append(self._constraint_decision_view(constraint))
        return {
            "goal": self._decision_view(current),
            "hierarchy": {
                "depth": len(ancestors),
                "ancestors": [self._decision_view(goal) for goal in ancestors],
                "children": [self._decision_view(goal) for goal in children],
            },
            "constraints": {
                "linked": linked_constraints,
                "unresolved_ids": unresolved_constraint_ids,
                "evidence_only": True,
                "must_not_issue_decision": True,
            },
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


class BusinessGoalRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = BusinessGoalProjector(event_store)
        self._constraints = BusinessConstraintProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="business_goal_fact",
            source="business_goal_registry",
            id_prefix="business-goal",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(goal: BusinessGoal) -> dict[str, object]:
        return {
            "schema_version": goal.schema_version,
            "goal_kind": goal.goal_kind,
            "target_key": goal.target_key,
            "metric": goal.metric,
            "baseline": goal.baseline,
            "target": goal.target,
            "deadline_at_ms": goal.deadline_at_ms,
            "owner_id": goal.owner_id,
            "constraint_ids": list(goal.constraint_ids),
            "parent_goal_id": goal.parent_goal_id,
            "priority": goal.priority,
        }

    @staticmethod
    def _state_token(goal: BusinessGoal) -> str:
        return "|".join(
            (
                goal.lifecycle_status.value,
                str(goal.updated_at_ms),
                str(goal.schema_version),
                goal.goal_kind,
                goal.metric or "",
                "" if goal.baseline is None else str(goal.baseline),
                "" if goal.target is None else str(goal.target),
                "" if goal.deadline_at_ms is None else str(goal.deadline_at_ms),
                goal.owner_id or "",
                ",".join(goal.constraint_ids),
                goal.parent_goal_id or "",
                str(goal.priority),
            )
        )

    def _validate_parent(self, *, tenant_id: str, business_id: str, goal_id: str, parent_goal_id: str | None) -> None:
        if parent_goal_id is None:
            return
        if str(parent_goal_id) == str(goal_id):
            raise ValueError("goal cannot be its own parent")
        try:
            parent = self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=parent_goal_id)
        except LookupError as exc:
            raise ValueError("parent_goal_id must reference a canonical goal in the same business") from exc
        if parent.lifecycle_status in {GoalLifecycleStatus.CANCELLED, GoalLifecycleStatus.ARCHIVED}:
            raise ValueError("parent_goal_id cannot reference cancelled or archived goal")

    def _validate_constraint_links(
        self,
        *,
        tenant_id: str,
        business_id: str,
        constraint_ids: tuple[str, ...],
    ) -> None:
        for constraint_id in constraint_ids:
            try:
                constraint = self._constraints.get(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    constraint_id=constraint_id,
                )
            except BusinessConstraintNotFound as exc:
                raise ValueError(
                    "constraint_ids must reference canonical constraints in the same business"
                ) from exc
            if constraint.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED:
                raise ValueError("constraint_ids cannot reference archived constraints")

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal_id: str,
        idempotency_key: str,
        goal_kind: str,
        target_key: str | None = None,
        metric: str | None = None,
        baseline: float | None = None,
        target: float | None = None,
        deadline_at_ms: int | None = None,
        owner_id: str | None = None,
        constraint_ids: tuple[str, ...] | list[str] = (),
        parent_goal_id: str | None = None,
        priority: int = 50,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessGoal:
        if isinstance(constraint_ids, str):
            raise ValueError("constraint_ids must be a sequence of canonical constraint ids")
        when = self._time(occurred_at_ms)
        candidate = BusinessGoal(
            goal_id=goal_id,
            tenant_id=tenant_id,
            business_id=business_id,
            goal_kind=goal_kind,
            target_key=target_key,
            metric=metric,
            baseline=baseline,
            target=target,
            deadline_at_ms=deadline_at_ms,
            owner_id=owner_id,
            constraint_ids=tuple(constraint_ids),
            parent_goal_id=parent_goal_id,
            priority=priority,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        replay = self._writer.find_existing_for_key(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=goal_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=GOAL_CREATED,
            event_metadata=event_metadata,
        )
        if replay is not None:
            envelope = dict(replay.get("payload") or {})
            persisted_payload = dict(envelope.get("payload") or {})
            persisted = BusinessGoal(
                goal_id=goal_id,
                tenant_id=tenant_id,
                business_id=business_id,
                goal_kind=persisted_payload.get("goal_kind"),
                target_key=persisted_payload.get("target_key"),
                parent_goal_id=persisted_payload.get("parent_goal_id"),
                priority=persisted_payload.get("priority", 50),
                schema_version=persisted_payload.get("schema_version", BUSINESS_GOAL_SCHEMA_VERSION),
                created_at_ms=int(envelope.get("event_time_ms") or replay.get("timestamp_ms") or 0),
                updated_at_ms=int(envelope.get("event_time_ms") or replay.get("timestamp_ms") or 0),
                metric=persisted_payload.get("metric"),
                baseline=persisted_payload.get("baseline"),
                target=persisted_payload.get("target"),
                deadline_at_ms=persisted_payload.get("deadline_at_ms"),
                owner_id=persisted_payload.get("owner_id"),
                constraint_ids=tuple(persisted_payload.get("constraint_ids") or ()),
            )
            if self._payload(persisted) != payload:
                raise ValueError(
                    "goal create idempotency key was already used with different objective data"
                )
            return self._projector.get(
                tenant_id=tenant_id,
                business_id=business_id,
                goal_id=goal_id,
            )
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("business goal already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
                operation="create", idempotency_key=idempotency_key, fact_type=GOAL_CREATED, payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._validate_parent(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            goal_id=candidate.goal_id,
            parent_goal_id=candidate.parent_goal_id,
        )
        self._validate_constraint_links(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            constraint_ids=candidate.constraint_ids,
        )
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
            operation="create", idempotency_key=idempotency_key, fact_type=GOAL_CREATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)

    def update_objective(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal_id: str,
        idempotency_key: str,
        baseline: object = _UNSET,
        target: object = _UNSET,
        deadline_at_ms: object = _UNSET,
        owner_id: object = _UNSET,
        constraint_ids: object = _UNSET,
        priority: object = _UNSET,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessGoal:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)
        if isinstance(constraint_ids, str):
            raise ValueError("constraint_ids must be a sequence of canonical constraint ids")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = replace(
            current,
            baseline=current.baseline if baseline is _UNSET else baseline,
            target=current.target if target is _UNSET else target,
            deadline_at_ms=current.deadline_at_ms if deadline_at_ms is _UNSET else deadline_at_ms,
            owner_id=current.owner_id if owner_id is _UNSET else owner_id,
            constraint_ids=(
                current.constraint_ids
                if constraint_ids is _UNSET
                else tuple(constraint_ids or ())
            ),
            priority=current.priority if priority is _UNSET else priority,
            updated_at_ms=when,
        )
        replay = self._writer.find_existing_for_key(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=goal_id,
            operation="update",
            idempotency_key=idempotency_key,
            fact_type=GOAL_UPDATED,
            event_metadata=event_metadata,
        )
        if replay is not None:
            persisted = dict(dict(replay.get("payload") or {}).get("payload") or {})
            requested_fields = {
                "baseline": baseline,
                "target": target,
                "deadline_at_ms": deadline_at_ms,
                "owner_id": owner_id,
                "constraint_ids": constraint_ids,
                "priority": priority,
            }
            for field_name, requested_value in requested_fields.items():
                if requested_value is _UNSET:
                    continue
                persisted_value = persisted.get(field_name)
                normalized_value = getattr(candidate, field_name)
                if field_name == "constraint_ids":
                    persisted_value = tuple(persisted_value or ())
                if persisted_value != normalized_value:
                    raise ValueError(
                        "goal update idempotency key was already used with different objective data"
                    )
            return current
        if current.lifecycle_status is not GoalLifecycleStatus.ACTIVE:
            raise ValueError("terminal business goal cannot be updated")
        if constraint_ids is not _UNSET and candidate.constraint_ids != current.constraint_ids:
            self._validate_constraint_links(
                tenant_id=tenant_id,
                business_id=business_id,
                constraint_ids=candidate.constraint_ids,
            )
        payload = self._payload(candidate)
        if payload == self._payload(current):
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
                operation="update", idempotency_key=idempotency_key, fact_type=GOAL_UPDATED,
                payload=payload, event_metadata=event_metadata,
            )
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
            expected_state_token=self._state_token(current), operation="update",
            idempotency_key=idempotency_key, fact_type=GOAL_UPDATED, payload=payload, occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)

    def update_priority(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal_id: str,
        idempotency_key: str,
        priority: int,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> BusinessGoal:
        return self.update_objective(
            tenant_id=tenant_id,
            business_id=business_id,
            goal_id=goal_id,
            idempotency_key=idempotency_key,
            priority=priority,
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
        )

    def _terminal(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal_id: str,
        idempotency_key: str,
        fact_type: str,
        operation: str,
        occurred_at_ms: int | None,
        event_metadata: dict[str, object] | None,
    ) -> BusinessGoal:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)
        target_status = {
            GOAL_COMPLETED: GoalLifecycleStatus.COMPLETED,
            GOAL_CANCELLED: GoalLifecycleStatus.CANCELLED,
            GOAL_ARCHIVED: GoalLifecycleStatus.ARCHIVED,
        }[fact_type]
        if current.lifecycle_status is not GoalLifecycleStatus.ACTIVE:
            if current.lifecycle_status is target_status:
                self._writer.repair_existing(
                    tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
                    operation=operation, idempotency_key=idempotency_key, fact_type=fact_type,
                    payload={"schema_version": BUSINESS_GOAL_SCHEMA_VERSION},
                    event_metadata=event_metadata,
                )
                return current
            raise ValueError("terminal business goal cannot change terminal status")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=goal_id,
            expected_state_token=self._state_token(current), operation=operation,
            idempotency_key=idempotency_key, fact_type=fact_type,
            payload={"schema_version": BUSINESS_GOAL_SCHEMA_VERSION}, occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)

    def complete(self, *, tenant_id: str, business_id: str, goal_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessGoal:
        return self._terminal(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id, idempotency_key=idempotency_key, fact_type=GOAL_COMPLETED, operation="complete", occurred_at_ms=occurred_at_ms, event_metadata=event_metadata)

    def cancel(self, *, tenant_id: str, business_id: str, goal_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessGoal:
        return self._terminal(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id, idempotency_key=idempotency_key, fact_type=GOAL_CANCELLED, operation="cancel", occurred_at_ms=occurred_at_ms, event_metadata=event_metadata)

    def archive(self, *, tenant_id: str, business_id: str, goal_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessGoal:
        return self._terminal(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id, idempotency_key=idempotency_key, fact_type=GOAL_ARCHIVED, operation="archive", occurred_at_ms=occurred_at_ms, event_metadata=event_metadata)

    def get(self, *, tenant_id: str, business_id: str, goal_id: str) -> BusinessGoal:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessGoal, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_BUSINESS_GOAL_LIFECYCLE_OWNER",
    "CANON_BUSINESS_GOAL_PROJECTOR",
    "GOAL_FACT_TYPES",
    "BusinessGoalHistoryInvariantViolation",
    "BusinessGoalProjector",
    "BusinessGoalRegistry",
]
