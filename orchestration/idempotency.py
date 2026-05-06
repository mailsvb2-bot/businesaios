from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set

from execution.primitives import SetIdempotencyGate


@dataclass
class Idempotency:
    seen_keys: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._gate = SetIdempotencyGate(self.seen_keys)

    def first_time(self, key: str) -> bool:
        return self._gate.claim(key)
