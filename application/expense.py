from __future__ import annotations

import time
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from core.finance.enums import ExpenseCategory, ExpenseLifecycleStatus
from core.finance.types import Expense
from reliability.idempotency_contract import IdempotencyStore

EXPENSE_SCHEMA_VERSION = 1
EXPENSE_RECORDED = "expense.recorded"
EXPENSE_VOIDED = "expense.voided"
EXPENSE_FACT_TYPES = frozenset({EXPENSE_RECORDED, EXPENSE_VOIDED})
CANON_EXPENSE_PROJECTOR = True
CANON_EXPENSE_LIFECYCLE_OWNER = True


class ExpenseNotFound(LookupError):
    pass


class ExpenseHistoryInvariantViolation(RuntimeError):
    pass


def _amount(value: Decimal | str | int | float) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("expense amount is invalid") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("expense amount must be positive and finite")
    return amount.normalize()


def _nonnegative_ms(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if normalized < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return normalized


def _currency(value: str) -> str:
    currency = str(value or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("expense currency must be a three-letter code")
    return currency


def _category(value: ExpenseCategory | str) -> ExpenseCategory:
    try:
        return value if isinstance(value, ExpenseCategory) else ExpenseCategory(str(value))
    except ValueError as exc:
        raise ValueError("expense category is invalid") from exc


def _schema(payload: dict[str, object]) -> None:
    if payload.get("schema_version") != EXPENSE_SCHEMA_VERSION:
        raise ExpenseHistoryInvariantViolation("expense schema version is unsupported")


class ExpenseProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, expense_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in EXPENSE_FACT_TYPES or (expense_id is not None and entity_id != str(expense_id)):
                continue
            if str(event.get("source") or "") != "expense_registry":
                raise ExpenseHistoryInvariantViolation("expense fact has a non-canonical source")
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (
            row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]
        ))
        return rows

    def get(self, *, tenant_id: str, business_id: str, expense_id: str) -> Expense:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)
        if not facts:
            raise ExpenseNotFound(f"expense not found: {expense_id}")
        recorded_rows = [row for row in facts if row["fact_type"] == EXPENSE_RECORDED]
        if len(recorded_rows) != 1 or facts[0] is not recorded_rows[0]:
            raise ExpenseHistoryInvariantViolation("expense history must begin with exactly one recorded fact")
        recorded = recorded_rows[0]
        payload = dict(recorded["payload"])
        _schema(payload)
        try:
            amount = _amount(payload.get("amount", ""))
            currency = _currency(str(payload.get("currency") or ""))
            category = _category(str(payload.get("category") or ""))
            incurred_at_ms = _nonnegative_ms(payload.get("incurred_at_ms"), "incurred_at_ms")
        except (TypeError, ValueError) as exc:
            raise ExpenseHistoryInvariantViolation("expense recorded payload is invalid") from exc
        expense = Expense(
            expense_id=str(expense_id), tenant_id=str(tenant_id), business_id=str(business_id),
            amount=amount, currency=currency, category=category, incurred_at_ms=incurred_at_ms,
            created_at_ms=int(recorded["event_time_ms"]), updated_at_ms=int(recorded["event_time_ms"]),
        )
        for row in facts[1:]:
            payload = dict(row["payload"])
            _schema(payload)
            if expense.lifecycle_status is ExpenseLifecycleStatus.VOIDED:
                raise ExpenseHistoryInvariantViolation("expense history continues after void")
            if row["fact_type"] != EXPENSE_VOIDED:
                raise ExpenseHistoryInvariantViolation("expense history contains an unknown transition")
            when = int(row["event_time_ms"])
            expense = replace(
                expense,
                lifecycle_status=ExpenseLifecycleStatus.VOIDED,
                updated_at_ms=max(expense.updated_at_ms, when),
                voided_at_ms=when,
            )
        return expense

    def list_for_business(self, *, tenant_id: str, business_id: str, include_voided: bool = False) -> tuple[Expense, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        expenses = tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)
            for expense_id in ids
        )
        return tuple(
            expense for expense in expenses
            if include_voided or expense.lifecycle_status is ExpenseLifecycleStatus.RECORDED
        )


class ExpenseRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = ExpenseProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="expense_fact",
            source="expense_registry",
            id_prefix="expense",
        )

    @staticmethod
    def _time(value: int | None = None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(expense: Expense) -> dict[str, object]:
        return {
            "schema_version": EXPENSE_SCHEMA_VERSION,
            "amount": format(expense.amount, "f"),
            "currency": expense.currency,
            "category": expense.category.value,
            "incurred_at_ms": int(expense.incurred_at_ms),
        }

    @staticmethod
    def _state_token(expense: Expense) -> str:
        return "|".join((
            expense.lifecycle_status.value,
            str(expense.updated_at_ms),
            format(expense.amount, "f"),
            expense.currency,
            expense.category.value,
            str(expense.incurred_at_ms),
        ))

    def record(
        self,
        *,
        tenant_id: str,
        business_id: str,
        expense_id: str,
        idempotency_key: str,
        amount: Decimal | str | int | float,
        currency: str,
        category: ExpenseCategory | str,
        incurred_at_ms: int,
        recorded_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Expense:
        tenant_id = str(tenant_id or "").strip()
        business_id = str(business_id or "").strip()
        expense_id = str(expense_id or "").strip()
        if not all((tenant_id, business_id, expense_id)):
            raise ValueError("expense tenant/business/id are required")
        when = self._time(recorded_at_ms)
        candidate = Expense(
            expense_id=expense_id,
            tenant_id=tenant_id,
            business_id=business_id,
            amount=_amount(amount),
            currency=_currency(currency),
            category=_category(category),
            incurred_at_ms=_nonnegative_ms(incurred_at_ms, "incurred_at_ms"),
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(
                tenant_id=tenant_id,
                business_id=business_id,
                expense_id=expense_id,
            )
        except ExpenseNotFound:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("expense already exists with different immutable financial data")
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=expense_id,
                operation="record",
                idempotency_key=idempotency_key,
                fact_type=EXPENSE_RECORDED,
                payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=expense_id,
            operation="record",
            idempotency_key=idempotency_key,
            fact_type=EXPENSE_RECORDED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)

    def void(
        self,
        *,
        tenant_id: str,
        business_id: str,
        expense_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Expense:
        current = self.get(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)
        if current.lifecycle_status is ExpenseLifecycleStatus.VOIDED:
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=expense_id,
                operation="void",
                idempotency_key=idempotency_key,
                fact_type=EXPENSE_VOIDED,
                payload={"schema_version": EXPENSE_SCHEMA_VERSION},
                event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=expense_id,
            expected_state_token=self._state_token(current),
            operation="void",
            idempotency_key=idempotency_key,
            fact_type=EXPENSE_VOIDED,
            payload={"schema_version": EXPENSE_SCHEMA_VERSION},
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)

    def get(self, *, tenant_id: str, business_id: str, expense_id: str) -> Expense:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, expense_id=expense_id)

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        include_voided: bool = False,
    ) -> tuple[Expense, ...]:
        return self._projector.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
            include_voided=include_voided,
        )


__all__ = [
    "CANON_EXPENSE_LIFECYCLE_OWNER",
    "CANON_EXPENSE_PROJECTOR",
    "EXPENSE_FACT_TYPES",
    "EXPENSE_RECORDED",
    "EXPENSE_SCHEMA_VERSION",
    "EXPENSE_VOIDED",
    "ExpenseHistoryInvariantViolation",
    "ExpenseNotFound",
    "ExpenseProjector",
    "ExpenseRegistry",
]
