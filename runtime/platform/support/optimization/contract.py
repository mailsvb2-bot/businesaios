from __future__ import annotations

"""External-only compatibility shim for the canonical optimization contracts owner.

Canonical owner: ``runtime.platform.support.optimization.contracts``.
"""

CANON_COMPAT_SHIM = True
CANON_EXTERNAL_ABI_ONLY = True

from runtime.platform.support.optimization.contracts import (
    CANONICAL_OPTIMIZATION_PUBLIC_MODULE,
    CANON_PLATFORM_OPTIMIZATION_PUBLIC_API,
    COMPAT_OPTIMIZATION_DECISION_MODULE,
    OptimizationGate,
    SOVEREIGN_DECISION_CORE,
)

__all__ = [
    "CANON_COMPAT_SHIM",
    "CANON_EXTERNAL_ABI_ONLY",
    "CANONICAL_OPTIMIZATION_PUBLIC_MODULE",
    "CANON_PLATFORM_OPTIMIZATION_PUBLIC_API",
    "COMPAT_OPTIMIZATION_DECISION_MODULE",
    "OptimizationGate",
    "SOVEREIGN_DECISION_CORE",
]
