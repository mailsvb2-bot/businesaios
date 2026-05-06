from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCapability:
    BOOT_OBSERVABILITY: str = "boot_observability"
    GOVERNANCE_COMPONENTS: str = "governance_components"
    DECISION_EXECUTION: str = "decision_execution"
    READ_DECISION_CORE: str = "read_decision_core"
