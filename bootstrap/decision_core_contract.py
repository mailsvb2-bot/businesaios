from __future__ import annotations

"""Boot-wiring compatibility surface for the canonical runtime decision contract.

This file stays explicit so boot-oriented tests and readers can see the contract
shape locally, while the canonical runtime application owner remains
``runtime.application.contracts``.
"""

from typing import Any, Protocol

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True
RUNTIME_DECISION_CORE_CONTRACT_VERSION = "RDC-CONTRACT-V1"


class RuntimeDecisionCorePort(Protocol):
    decide: Any

    def issue(self, state: Any) -> Any: ...


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "RUNTIME_DECISION_CORE_CONTRACT_VERSION",
    "RuntimeDecisionCorePort",
]
