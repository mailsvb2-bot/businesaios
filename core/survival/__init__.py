"""Compatibility package surface: ``core.survival`` -> ``survival``.

The package root keeps the historical imports alive while the canonical owners
live in the top-level ``survival`` package.
"""

from __future__ import annotations

import sys
from importlib import import_module

from survival.controller import SurvivalController, SurvivalMode, SurvivalVerdict
from survival.metrics import SurvivalMetrics

CANON_TRANSITION_SURFACE = True
CANON_COMPAT_SHIM = True
CANONICAL_OWNER_PACKAGE = "survival"

_COMPAT_ALIAS_MAP = {
    "controller": "survival.controller",
    "metrics": "survival.metrics",
}

for _alias_name, _target_module_name in _COMPAT_ALIAS_MAP.items():
    _target = import_module(_target_module_name)
    sys.modules[f"{__name__}.{_alias_name}"] = _target
    globals()[_alias_name] = _target


__all__ = [
    "CANON_TRANSITION_SURFACE",
    "CANON_COMPAT_SHIM",
    "CANONICAL_OWNER_PACKAGE",
    "SurvivalController",
    "SurvivalMode",
    "SurvivalVerdict",
    "SurvivalMetrics",
]
