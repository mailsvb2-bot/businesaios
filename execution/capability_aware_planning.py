"""Compatibility shim for the canonical capability router/planner surface.

Canonical owner logic lives in the application capability modules, but the
execution namespace remains the stable public import surface. Keep this file
thin and make the dependency on ``execution.capability_router`` explicit so
arch-lock tests can verify that planner callers stay routed through the
canonical execution-facing owner path.
"""

from __future__ import annotations



from execution.capability_router import ExecutionCapabilityRouter
from application.capability.capability_aware_planning import (
    CANON_CAPABILITY_AWARE_PLANNING,
    CapabilityAwarePlanner,
    CapabilityPlanDecision,
)

CANON_CAPABILITY_COMPAT_SURFACE = True
# Compatibility shim: canonical public owner path remains execution.capability_router.


__all__ = [
    'CANON_CAPABILITY_COMPAT_SURFACE',
    'CANON_CAPABILITY_AWARE_PLANNING',
    'ExecutionCapabilityRouter',
    'CapabilityAwarePlanner',
    'CapabilityPlanDecision',
]
