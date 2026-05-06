from __future__ import annotations

from dataclasses import dataclass, field

from execution.primitives import SetIdempotencyGate


@dataclass
class ActionIdempotency:
    seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._gate = SetIdempotencyGate(self.seen)

    def allow(self, action_id: str) -> bool:
        return self._gate.claim(action_id)
