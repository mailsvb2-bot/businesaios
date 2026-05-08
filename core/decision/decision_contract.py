from __future__ import annotations

"""Thin compatibility re-export for application.decision.decision_contract.

This module preserves the historical core.decision.decision_contract import path
without creating a second decision contract owner.
"""

from application.decision.decision_contract import (
    NON_SOVEREIGN_ENGINE_ROLE,
    build_executable_action_payload,
    canonical_request,
    start_trace,
)

CANON_COMPAT_SHIM = True
CANONICAL_OWNER_MODULE = "application.decision.decision_contract"

__all__ = [
    "CANON_COMPAT_SHIM",
    "CANONICAL_OWNER_MODULE",
    "NON_SOVEREIGN_ENGINE_ROLE",
    "build_executable_action_payload",
    "canonical_request",
    "start_trace",
]
