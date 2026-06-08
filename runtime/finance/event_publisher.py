from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable


@dataclass(frozen=True)
class PublishedFinanceEvent:
    event_name: str
    correlation_id: str
    tenant_id: str
    payload: dict[str, Any]


FinanceEventSubscriber = Callable[[PublishedFinanceEvent], None]

logger = logging.getLogger(__name__)


def _required_token(value: str, field_name: str) -> str:
    token = str(value or '').strip()
    if not token:
        raise ValueError(f'{field_name}_required')
    return token


class FinanceEventPublisher:
    def __init__(self) -> None:
        self._events: list[PublishedFinanceEvent] = []
        self._subscribers: list[FinanceEventSubscriber] = []

    def subscribe(self, subscriber: FinanceEventSubscriber) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: FinanceEventSubscriber) -> None:
        try:
            self._subscribers.remove(subscriber)
        except ValueError:
            return

    def publish(
        self,
        event_name: str,
        *,
        correlation_id: str,
        tenant_id: str,
        payload: dict[str, Any],
    ) -> None:
        event = PublishedFinanceEvent(
            event_name=_required_token(event_name, 'event_name'),
            correlation_id=_required_token(correlation_id, 'correlation_id'),
            tenant_id=_required_token(tenant_id, 'tenant_id'),
            payload=dict(payload),
        )
        self._events.append(event)
        for subscriber in tuple(self._subscribers):
            try:
                subscriber(event)
            except Exception:
                logger.warning('finance_event_subscriber_failed', exc_info=True)

    def all(self) -> tuple[PublishedFinanceEvent, ...]:
        return tuple(self._events)
