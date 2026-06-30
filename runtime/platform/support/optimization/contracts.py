"""Canonical optimization contracts re-export surface.

This module exists because historical callers import the public contract symbols
from ``runtime.platform.support.optimization.contracts`` while the canonical
owner is the package root. Keep this file as a thin, explicit re-export layer.
"""

from __future__ import annotations

from . import (
    CANON_PLATFORM_OPTIMIZATION_PUBLIC_API,
    CANONICAL_OPTIMIZATION_PUBLIC_MODULE,
    COMPAT_OPTIMIZATION_DECISION_MODULE,
    SOVEREIGN_DECISION_CORE,
    OptimizationGate,
)

CANON_COMPAT_SHIM = True
__all__ = [
    'CANONICAL_OPTIMIZATION_PUBLIC_MODULE',
    'CANON_PLATFORM_OPTIMIZATION_PUBLIC_API',
    'COMPAT_OPTIMIZATION_DECISION_MODULE',
    'OptimizationGate',
    'SOVEREIGN_DECISION_CORE',
]

