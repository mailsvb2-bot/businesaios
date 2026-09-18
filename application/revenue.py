from __future__ import annotations

import time
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from core.finance.enums import RevenueLifecycleStatus
from core.finance.types import Revenue
from reliability.idempotency_contract import IdempotencyStore

REVENUE_SCHEMA_VERSION = 1
REVENUE_RECOGNIZED = "revenue.recognized"
REVENUE_REVERSED = "revenue.reversed"
REVENUE_FACT_TYPES = frozenset({REVENUE_RECOGNIZED, REVENUE_REVERSED})
CANON_REVENUE_PROJECTOR = True
CANON_REVENUE_LIFECYCLE_OWNER = True


class RevenueNotFound(LookupError):
    pass


class RevenueHistoryInvariantViolation(RuntimeError):
    pass


def _amount(value: Decimal | str | int | float) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("revenue amount is invalid") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("revenue amount must be positive and finite")
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
        raise ValueError("revenue currency must be a three-letter code")
    return currency


def _token(value: object, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid revenue {field}")
    return text


def _schema(payload: dict[str, object]) -> None:
    if payload.get("schema_version") != REVENUE_SCHEMA_VERSION:
        raise RevenueHistoryInvariantViolation("revenue schema version is unsupported")


class RevenueProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self,
        *,
        tenant_id: str,
        business_id: str,
        revenue_id: str | None = None,
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
            if fact_type not in REVENUE_FACT_TYPES:
                continue
            if revenue_id is not None and entity_id != str(revenue_id):
                continue
            if str(event.get("source") or "") != "revenue_registry":
                raise RevenueHistoryInvariantViolation("revenue fact has a non-canonical source")
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(
                        envelope.get("event_time_ms") or event.get("timestamp_ms") or 0
                    ),
                    "observed_at_ms": int(
                        envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0
                    ),
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

    def get(self, *, tenant_id: str, business_id: str, revenue_id: str) -> Revenue:
        facts = self._facts(
            tenant_id=tenant_id,
            business_id=business_id,
            revenue_id=revenue_id,
        )
        if not facts:
            raise RevenueNotFound(f"revenue not found: {revenue_id}")
        recognized_rows = [row for row in facts if row["fact_type"] == REVENUE_RECOGNIZED]
        if len(recognized_rows) != 1 or facts[0] is not recognized_rows[0]:
            raise RevenueHistoryInvariantViolation(
                "revenue history must begin with exactly one recognized fact"
            )
        recognized = recognized_rows[0]
        payload = dict(recognized["payload"])
        _schema(payload)
        try:
            amount = _amount(payload.get("amount", ""))
            currency = _currency(str(payload.get("currency") or ""))
            source_kind = _token(payload.get("source_kind"), "source_kind")
            source_id = _token(payload.get("source_id"), "source_id")
            recognized_at_ms = _nonnegative_ms(
                payload.get("recognized_at_ms"), "recognized_at_ms"
            )
        except (TypeError, ValueError) as exc:
            raise RevenueHistoryInvariantViolation(
                "revenue recognized payload is invalid"
            ) from exc
        revenue = Revenue(
            revenue_id=str(revenue_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            amount=amount,
            currency=currency,
            source_kind=source_kind,
            source_id=source_id,
            recognized_at_ms=recognized_at_ms,
            created_at_ms=int(recognized["event_time_ms"]),
            updated_at_ms=int(recognized["event_time_ms"]),
        )
        for row in facts[1:]:
            transition_payload = dict(row["payload"])
            _schema(transition_payload)
            if revenue.lifecycle_status is RevenueLifecycleStatus.REVERSED:
                raise RevenueHistoryInvariantViolation("revenue history continues after reversal")
            if row["fact_type"] != REVENUE_REVERSED:
                raise RevenueHistoryInvariantViolation(
                    "revenue history contains an unknown transition"
                )
            when = int(row["event_time_ms"])
            revenue = replace(
                revenue,
                lifecycle_status=RevenueLifecycleStatus.REVERSED,
                updated_at_ms=max(revenue.updated_at_ms, when),
                reversed_at_ms=when,
            )
        return revenue

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        include_reversed: bool = False,
    ) -> tuple[Revenue, ...]:
        ids = sorted(
            {
                str(row["entity_id"])
                for row in self._facts(tenant_id=tenant_id, business_id=business_id)
            }
        )
        rows = tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, revenue_id=revenue_id)
            for revenue_id in ids
        )
        return tuple(
            row
            for row in rows
            if include_reversed
            or row.lifecycle_status is RevenueLifecycleStatus.RECOGNIZED
        )


class RevenueRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = RevenueProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="revenue_fact",
            source="revenue_registry",
            id_prefix="revenue",
        )

    @staticmethod
    def _time(value: int | None = None) -> int:
        return int(time.time() * 1000) if value is None else _nonnegative_ms(value, "occurred_at_ms")

    @staticmethod
    def _payload(revenue: Revenue) -> dict[str, object]:
        return {
            "schema_version": REVENUE_SCHEMA_VERSION,
            "amount": format(revenue.amount, "f"),
            "currency": revenue.currency,
            "source_kind": revenue.source_kind,
            "source_id": revenue.source_id,
            "recognized_at_ms": int(revenue.recognized_at_ms),
        }

    @staticmethod
    def _state_token(revenue: Revenue) -> str:
        return "|".join(
            (
                revenue.lifecycle_status.value,
                str(revenue.updated_at_ms),
                format(revenue.amount, "f"),
                revenue.currency,
                revenue.source_kind,
                revenue.source_id,
                str(revenue.recognized_at_ms),
            )
        )

    def recognize(
        self,
        *,
        tenant_id: str,
        business_id: str,
        revenue_id: str,
        idempotency_key: str,
        amount: Decimal | str | int | float,
        currency: str,
        source_kind: str,
        source_id: str,
        recognized_at_ms: int,
        recorded_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Revenue:
        tenant_id = _token(tenant_id, "tenant_id")
        business_id = _token(business_id, "business_id")
        revenue_id = _token(revenue_id, "revenue_id")
        when = self._time(recorded_at_ms)
        candidate = Revenue(
            revenue_id=revenue_id,
            tenant_id=tenant_id,
            business_id=business_id,
            amount=_amount(amount),
            currency=_currency(currency),
            source_kind=_token(source_kind, "source_kind"),
            source_id=_token(source_id, "source_id"),
            recognized_at_ms=_nonnegative_ms(recognized_at_ms, "recognized_at_ms"),
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(
                tenant_id=tenant_id,
                business_id=business_id,
                revenue_id=revenue_id,
            )
        except RevenueNotFound:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError(
                    "revenue already exists with different immutable recognition data"
                )
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=revenue_id,
                operation="recognize",
                idempotency_key=idempotency_key,
                fact_type=REVENUE_RECOGNIZED,
                payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=revenue_id,
            operation="recognize",
            idempotency_key=idempotency_key,
            fact_type=REVENUE_RECOGNIZED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, revenue_id=revenue_id)

    def reverse(
        self,
        *,
        tenant_id: str,
        business_id: str,
        revenue_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Revenue:
        current = self.get(
            tenant_id=tenant_id,
            business_id=business_id,
            revenue_id=revenue_id,
        )
        if current.lifecycle_status is RevenueLifecycleStatus.REVERSED:
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=revenue_id,
                operation="reverse",
                idempotency_key=idempotency_key,
                fact_type=REVENUE_REVERSED,
                payload={"schema_version": REVENUE_SCHEMA_VERSION},
                event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=revenue_id,
            expected_state_token=self._state_token(current),
            operation="reverse",
            idempotency_key=idempotency_key,
            fact_type=REVENUE_REVERSED,
            payload={"schema_version": REVENUE_SCHEMA_VERSION},
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, revenue_id=revenue_id)

    def get(self, *, tenant_id: str, business_id: str, revenue_id: str) -> Revenue:
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            revenue_id=revenue_id,
        )

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        include_reversed: bool = False,
    ) -> tuple[Revenue, ...]:
        return self._projector.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
            include_reversed=include_reversed,
        )


__all__ = [
    "CANON_REVENUE_LIFECYCLE_OWNER",
    "CANON_REVENUE_PROJECTOR",
    "REVENUE_FACT_TYPES",
    "REVENUE_RECOGNIZED",
    "REVENUE_REVERSED",
    "REVENUE_SCHEMA_VERSION",
    "RevenueHistoryInvariantViolation",
    "RevenueNotFound",
    "RevenueProjector",
    "RevenueRegistry",
]
