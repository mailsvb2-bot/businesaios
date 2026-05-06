from __future__ import annotations


class InMemoryCrmWebhookDedupStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def first_seen(self, event_id: str) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        return True
