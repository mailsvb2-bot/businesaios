"""Event-sourced RL pricing helpers."""

from __future__ import annotations

import sys
from importlib import import_module

CANON_COMPAT_SHIM = True

_COMPAT_ALIAS_MAP = {
    "selector": "core.scorers.pricing",
}

for _alias_name, _target_module_name in _COMPAT_ALIAS_MAP.items():
    _target = import_module(_target_module_name)
    sys.modules[f"{__name__}.{_alias_name}"] = _target
    globals()[_alias_name] = _target
