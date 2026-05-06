from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Capability:
    name: str
    description: str

CAPABILITIES: Tuple[Capability, ...] = (
    Capability("score", "compute candidate scores"),
    Capability("observe", "attach reward or metrics"),
    Capability("rank", "order candidates"),
    Capability("validate", "check policy safety"),
    Capability("recommend", "produce recommendation sets"),
)

def capability_names() -> tuple[str, ...]:
    return tuple(c.name for c in CAPABILITIES)
