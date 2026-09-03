from __future__ import annotations

from typing import Any

from contracts.customer import CustomerNotFound, CustomerTimeline, CustomerTimelineEntry
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

CANON_CUSTOMER_TIMELINE_PROJECTION = True

_CUSTOMER_TITLES = {
    "customer.created": "Customer created",
    "customer.identity.attached": "Customer identity linked",
    "customer.contact.observed": "Customer contact observed",
    "customer.archived": "Customer archived",
}


class CustomerTimelineInvariantViolation(RuntimeError):
    pass


class CustomerTimelineProjector:
    """Read-only timeline projection. EventStore remains the only chronology truth."""

    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    @staticmethod
    def _amount(payload: dict[str, Any]) -> tuple[int | None, str | None]:
        value = payload.get("amount_minor")
        if value is None:
            return None, None
        if isinstance(value, bool) or not isinstance(value, int):
            raise CustomerTimelineInvariantViolation("amount_minor must be integer")
        currency = str(payload.get("currency") or "").strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise CustomerTimelineInvariantViolation("monetary event requires currency")
        return value, currency

    def get(self, *, tenant_id: str, business_id: str, customer_id: str) -> CustomerTimeline:
        entries: list[tuple[int, CustomerTimelineEntry]] = []
        customer_seen = False
        seen_sources: set[str] = set()
        for append_order, event in enumerate(self._events.iter_events(tenant_id=tenant_id, start_ms=0)):
            event_type = str(event.get("event_type") or event.get("type") or "").strip()
            source_id = str(event.get("event_id") or "").strip()
            timestamp = event.get("timestamp_ms")
            if not source_id or timestamp is None:
                continue
            payload = dict(event.get("payload") or {})
            kind, title, detail, relevant = event_type, event_type.replace("_", " ").strip() or "Business event", None, False
            if event_type == BUSINESS_FACT_EVENT_TYPE:
                if str(payload.get("business_id") or "") != business_id or str(payload.get("entity_id") or "") != customer_id:
                    continue
                fact_type = str(payload.get("fact_type") or "").strip()
                if not fact_type.startswith("customer."):
                    continue
                fact_payload = dict(payload.get("payload") or {})
                kind, title, relevant = fact_type, _CUSTOMER_TITLES.get(fact_type, fact_type), True
                customer_seen = customer_seen or fact_type == "customer.created"
                if fact_type in {"customer.identity.attached", "customer.contact.observed"}:
                    detail = str(fact_payload.get("channel") or "").strip() or None
                timestamp = payload.get("event_time_ms", event.get("timestamp_ms"))
                payload = fact_payload
            else:
                if str(payload.get("business_id") or "") != business_id or str(payload.get("customer_id") or "") != customer_id:
                    continue
                relevant = True
            if not relevant or source_id in seen_sources:
                continue
            try:
                occurred_at_ms = int(timestamp)
            except (TypeError, ValueError) as exc:
                raise CustomerTimelineInvariantViolation("customer timeline timestamp is invalid") from exc
            amount_minor, currency = self._amount(payload)
            entries.append((append_order, CustomerTimelineEntry(
                kind=kind, occurred_at_ms=occurred_at_ms, source_type=event_type, source_id=source_id,
                title=title, detail=detail, amount_minor=amount_minor, currency=currency,
                correlation_id=None if event.get("correlation_id") is None else str(event.get("correlation_id")),
                metadata={"source": str(event.get("source") or "")},
            )))
            seen_sources.add(source_id)
        if not customer_seen:
            raise CustomerNotFound("customer was not found in the active business")
        entries.sort(key=lambda item: (item[1].occurred_at_ms, item[0], item[1].source_id))
        return CustomerTimeline(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id, entries=tuple(item for _, item in entries))


__all__ = ["CANON_CUSTOMER_TIMELINE_PROJECTION", "CustomerTimelineInvariantViolation", "CustomerTimelineProjector"]
