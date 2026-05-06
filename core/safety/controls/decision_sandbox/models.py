from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SandboxOutcome:
    passed: bool
    findings: tuple[str, ...] = field(default_factory=tuple)
    evidence: dict[str, Any] = field(default_factory=dict)
