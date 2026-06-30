"""Compatibility shim for the canonical execution-facing capability router.

The implementation owner lives in ``application.capability.capability_router``,
but the execution namespace is the stable import surface used across the repo.
Keep this file thin, explicit, and dependent only on canonical execution-facing
facades so arch-lock tests can prove that planner call sites do not grow a
parallel capability subsystem.
"""

from __future__ import annotations



from execution.capability_matrix import CapabilityMatrix, CapabilityRecord
from execution.capability_health_registry import CapabilityHealthRegistry
from execution.capability_diagnostics import CapabilityDiagnosticsBuilder
from application.capability.capability_router import (
    CANON_EXECUTION_CAPABILITY_ROUTER,
    ExecutionCapabilityRouter,
    RoutedCapabilityAction,
)

CANON_CAPABILITY_COMPAT_SURFACE = True
# Compatibility shim: canonical public owner path remains execution.capability_router.


__all__ = [
    'CANON_CAPABILITY_COMPAT_SURFACE',
    'CANON_EXECUTION_CAPABILITY_ROUTER',
    'CapabilityMatrix',
    'CapabilityRecord',
    'CapabilityHealthRegistry',
    'CapabilityDiagnosticsBuilder',
    'ExecutionCapabilityRouter',
    'RoutedCapabilityAction',
]
