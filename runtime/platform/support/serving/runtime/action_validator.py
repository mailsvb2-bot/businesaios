from __future__ import annotations

import importlib
from typing import Any

CANON_COMPAT_SHIM = True
CANON_EXTERNAL_ABI_ONLY = True

_OWNER = "application.decision.action_validator"
_OWNER_ALL = tuple(importlib.import_module(_OWNER).__all__)


def __getattr__(name: str) -> Any:
    if name not in _OWNER_ALL:
        raise AttributeError(name)
    value = getattr(importlib.import_module(_OWNER), name)
    globals()[name] = value
    return value


__all__ = list(_OWNER_ALL)
