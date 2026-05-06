from __future__ import annotations

import sys
from importlib import import_module

from core.creative_intelligence.snapshot_builder import build_creative_snapshot

CANON_COMPAT_SHIM = True

_COMPAT_ALIAS_MAP = {
    "portfolio_ranker": "core.scorers.portfolio",
}

for _alias_name, _target_module_name in _COMPAT_ALIAS_MAP.items():
    _target = import_module(_target_module_name)
    sys.modules[f"{__name__}.{_alias_name}"] = _target
    globals()[_alias_name] = _target

__all__ = ["CANON_COMPAT_SHIM", "build_creative_snapshot"]
