from __future__ import annotations

"""Single boot/runtime typing contract for the sovereign decision issuer.

The canonical production ``DecisionCore`` exposes both methods. Compatibility
surfaces may supply either ``issue`` or ``optimize``; both are aliases into the
same single decision owner and never represent separate decision engines.
"""

from collections.abc import Callable
from typing import Any, Protocol, TypeAlias, runtime_checkable

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True
CANON_RUNTIME_DECISION_CORE_SINGLE_CONTRACT = True
RUNTIME_DECISION_CORE_CONTRACT_VERSION = "RDC-CONTRACT-V1"
RUNTIME_DECISION_CORE_COMPAT_METHODS = ("issue", "optimize")


@runtime_checkable
class RuntimeDecisionIssuePort(Protocol):
    issue: Callable[[Any], Any]


@runtime_checkable
class RuntimeDecisionOptimizePort(Protocol):
    optimize: Callable[[Any], Any]


RuntimeDecisionCorePort: TypeAlias = (
    RuntimeDecisionIssuePort | RuntimeDecisionOptimizePort
)


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_BOOT_CLUSTER_FINAL_OWNER",
    "CANON_RUNTIME_DECISION_CORE_SINGLE_CONTRACT",
    "RUNTIME_DECISION_CORE_CONTRACT_VERSION",
    "RUNTIME_DECISION_CORE_COMPAT_METHODS",
    "RuntimeDecisionCorePort",
    "RuntimeDecisionIssuePort",
    "RuntimeDecisionOptimizePort",
]
