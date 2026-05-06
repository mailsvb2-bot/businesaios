from __future__ import annotations
from kernel.decision_result import DecisionResult
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus
from observability.events import Event


class DecisionPublisher:
    def __init__(self, audit_log: DecisionAuditLog, event_bus: EventBus) -> None:
        self._audit_log = audit_log
        self._event_bus = event_bus

    def publish(self, result: DecisionResult) -> None:
        payload = result.as_dict()
        self._audit_log.record(result)
        self._event_bus.publish(Event(event_type='decision.published', payload=payload))
