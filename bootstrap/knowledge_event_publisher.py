from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_KNOWLEDGE_EVENT_PUBLISHER_FINAL_OWNER = True


from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryKnowledgeEventPublisher:
    events: list[Any] = field(default_factory=list)

    def publish(self, event: object) -> None:
        self.events.append(event)
