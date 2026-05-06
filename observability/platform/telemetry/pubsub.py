from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Iterable, MutableMapping, TypeVar

T = TypeVar('T')


@dataclass
class TopicSubscriberRegistry(Generic[T]):
    _subscribers: MutableMapping[str, list[Callable[[T], None]]] = field(default_factory=dict)

    def subscribe(self, topic: str, callback: Callable[[T], None]) -> None:
        normalized = topic.strip()
        if not normalized:
            raise ValueError('topic must not be empty')
        self._subscribers.setdefault(normalized, []).append(callback)

    def fanout(self, topic: str, item: T) -> None:
        for callback in tuple(self._subscribers.get(topic, ())):
            callback(item)

    def snapshot(self) -> dict[str, list[Callable[[T], None]]]:
        return {topic: list(callbacks) for topic, callbacks in self._subscribers.items()}


@dataclass
class AppendOnlyTopicLog(Generic[T]):
    _topics: MutableMapping[str, list[T]] = field(default_factory=dict)

    def append(self, topic: str, item: T) -> None:
        normalized = topic.strip()
        if not normalized:
            raise ValueError('topic must not be empty')
        self._topics.setdefault(normalized, []).append(item)

    def events(self, topic: str) -> list[T]:
        normalized = topic.strip()
        if not normalized:
            raise ValueError('topic must not be empty')
        return list(self._topics.get(normalized, ()))

    def topics(self) -> Iterable[str]:
        return tuple(self._topics.keys())
