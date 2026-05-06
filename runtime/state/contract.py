from __future__ import annotations

"""Canonical runtime contract for truthful state synthesis.

This package is a synthesis layer only. It cannot own or execute decisions and
must remain subordinate to the canonical world-state/decision path.
"""

RUNTIME_STATE_PUBLIC_API = True
STATE_SYNTHESIS_CANON = "runtime.state"
STATE_SYNTHESIS_SUBORDINATE_TO_WORLD_STATE = True
STATE_SYNTHESIS_FORBIDS_DECISION_OWNERSHIP = True

__all__ = [
    "RUNTIME_STATE_PUBLIC_API",
    "STATE_SYNTHESIS_CANON",
    "STATE_SYNTHESIS_SUBORDINATE_TO_WORLD_STATE",
    "STATE_SYNTHESIS_FORBIDS_DECISION_OWNERSHIP",
]
