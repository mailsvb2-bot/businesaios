from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeServiceType:
    GUARD: str = "guard"
    GOVERNANCE: str = "governance"
    EXECUTOR: str = "executor"
    CORE: str = "core"
