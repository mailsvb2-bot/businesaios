"""Compatibility re-export of the single canonical decision-core contract."""

from __future__ import annotations

from bootstrap.decision_core_contract import (
    CANON_RUNTIME_DECISION_CORE_SINGLE_CONTRACT,
    RUNTIME_DECISION_CORE_COMPAT_METHODS,
    RUNTIME_DECISION_CORE_CONTRACT_VERSION,
    RuntimeDecisionCorePort,
    RuntimeDecisionIssuePort,
    RuntimeDecisionOptimizePort,
)

CANON_RUNTIME_DECISION_CORE_CONTRACT = True
CANON_RUNTIME_DECISION_CORE_CONTRACT_REEXPORT = True


__all__ = [
    "RUNTIME_DECISION_CORE_CONTRACT_VERSION",
    "RUNTIME_DECISION_CORE_COMPAT_METHODS",
    "CANON_RUNTIME_DECISION_CORE_CONTRACT",
    "CANON_RUNTIME_DECISION_CORE_CONTRACT_REEXPORT",
    "CANON_RUNTIME_DECISION_CORE_SINGLE_CONTRACT",
    "RuntimeDecisionCorePort",
    "RuntimeDecisionIssuePort",
    "RuntimeDecisionOptimizePort",
]
