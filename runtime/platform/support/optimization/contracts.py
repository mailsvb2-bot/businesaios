from __future__ import annotations

"""Canonical optimization contracts re-export surface.

This module exists because historical callers import the public contract symbols
from ``runtime.platform.support.optimization.contracts`` while the canonical
owner is the package root. Keep this file as a thin, explicit re-export layer.
"""

from . import (
    CANONICAL_OPTIMIZATION_PUBLIC_MODULE,
    CANON_PLATFORM_OPTIMIZATION_PUBLIC_API,
    COMPAT_OPTIMIZATION_DECISION_MODULE,
    OptimizationGate,
    SOVEREIGN_DECISION_CORE,
)

__all__ = [
    'CANONICAL_OPTIMIZATION_PUBLIC_MODULE',
    'CANON_PLATFORM_OPTIMIZATION_PUBLIC_API',
    'COMPAT_OPTIMIZATION_DECISION_MODULE',
    'OptimizationGate',
    'SOVEREIGN_DECISION_CORE',
]
