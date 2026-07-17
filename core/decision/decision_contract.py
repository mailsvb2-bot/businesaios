"""Thin compatibility re-export for the recommendation-only decision contract.

This module preserves the historical ``core.decision.decision_contract`` import
path without creating a second owner or reintroducing executable-action shaping.
"""

from __future__ import annotations

from application.decision.decision_contract import (
    CANON_RECOMMENDATION_CONTRACT_NO_EXECUTABLE_ACTION,
    NON_SOVEREIGN_ENGINE_ROLE,
    NON_SOVEREIGN_ENGINE_SURFACE,
    canonical_request,
    start_trace,
)

CANON_COMPAT_SHIM = True
CANONICAL_OWNER_MODULE = "application.decision.decision_contract"

__all__ = [
    "CANON_COMPAT_SHIM",
    "CANONICAL_OWNER_MODULE",
    "CANON_RECOMMENDATION_CONTRACT_NO_EXECUTABLE_ACTION",
    "NON_SOVEREIGN_ENGINE_ROLE",
    "NON_SOVEREIGN_ENGINE_SURFACE",
    "canonical_request",
    "start_trace",
]
