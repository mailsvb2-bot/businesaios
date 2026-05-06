from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.events import EventLog
from runtime.finance.event_publisher import PublishedFinanceEvent


@dataclass(frozen=True)
class ConsumedFinanceEvent:
    event_name: str
    correlation_id: str
    tenant_id: str
    source: str


class FinanceEventLogSink:
    def __init__(self, *, event_log: EventLog) -> None:
        self._event_log = event_log
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    def consume(self, event: PublishedFinanceEvent) -> None:
        if self._event_log is None or not hasattr(self._event_log, "emit"):
            return
        self._event_log.emit(
            event_type=event.event_name,
            source='runtime.finance',
            user_id=f'finance:{event.tenant_id}',
            payload=dict(event.payload),
            correlation_id=event.correlation_id,
        )
        self._count += 1


class FinanceEventReadModel:
    def __init__(self) -> None:
        self._items: dict[str, ConsumedFinanceEvent] = {}

    def consume(self, event: PublishedFinanceEvent) -> None:
        key = f'{event.tenant_id}:{event.correlation_id}:{event.event_name}'
        self._items[key] = ConsumedFinanceEvent(
            event_name=event.event_name,
            correlation_id=event.correlation_id,
            tenant_id=event.tenant_id,
            source='runtime.finance',
        )

    def all(self) -> dict[str, ConsumedFinanceEvent]:
        return dict(self._items)


class FinanceObservabilitySink:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._correlations: dict[str, tuple[str, ...]] = {}

    def consume(self, event: PublishedFinanceEvent) -> None:
        self._counters[event.event_name] = self._counters.get(event.event_name, 0) + 1
        key = f'{event.tenant_id}:{event.correlation_id}'
        existing = list(self._correlations.get(key, ()))
        existing.append(event.event_name)
        self._correlations[key] = tuple(existing)

    def counters(self) -> dict[str, int]:
        return dict(self._counters)

    def correlation_events(self, tenant_id: str, correlation_id: str) -> tuple[str, ...]:
        return self._correlations.get(f'{tenant_id}:{correlation_id}', ())
