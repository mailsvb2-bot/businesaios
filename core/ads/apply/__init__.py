from __future__ import annotations

import sys
from importlib import import_module

from core.ads.apply_engine import AdsApplyEngine, AdsApplyEnv

CANON_COMPAT_SHIM = True

_COMPAT_ALIAS_MAP = {
    "engine": "core.ads.apply_engine",
}

for _alias_name, _target_module_name in _COMPAT_ALIAS_MAP.items():
    _target = import_module(_target_module_name)
    sys.modules[f"{__name__}.{_alias_name}"] = _target
    globals()[_alias_name] = _target

__all__ = ["CANON_COMPAT_SHIM", "AdsApplyEngine", "AdsApplyEnv"]
