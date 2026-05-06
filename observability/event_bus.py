from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List

from observability.events import Event
from observability.platform.telemetry.pubsub import AppendOnlyTopicLog, TopicSubscriberRegistry


@dataclass
class EventBus:
    events: List[Event] = field(default_factory=list)
    subscribers: Dict[str, List[Callable[[Event], None]]] = field(default_factory=dict)
    _topic_log: AppendOnlyTopicLog[Event] = field(default_factory=AppendOnlyTopicLog, repr=False)
    _subscriber_registry: TopicSubscriberRegistry[Event] = field(default_factory=TopicSubscriberRegistry, repr=False)

    def publish(self, event: Event) -> None:
        self.events.append(event)
        self._topic_log.append(event.event_type, event)
        self._subscriber_registry.fanout(event.event_type, event)
        self.subscribers = self._subscriber_registry.snapshot()

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        self._subscriber_registry.subscribe(event_type, callback)
        self.subscribers = self._subscriber_registry.snapshot()

    def published_types(self) -> Iterable[str]:
        return tuple(event.event_type for event in self.events)

    def events_for_type(self, event_type: str) -> List[Event]:
        return self._topic_log.events(event_type)
