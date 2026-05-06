from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_CORE_PLANS_OWNER = True
_OWNER_MODULE = 'core.plans.catalog'
_OWNER_EXPORTS = ['active_plans', 'get_plan_by_id', 'load_plans', 'plan_by_id']


def _owner() -> Any:
    return import_module(_OWNER_MODULE)


def __getattr__(name: str) -> Any:
    if name == 'CANON_CORE_PLANS_OWNER':
        return CANON_CORE_PLANS_OWNER
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))


__all__ = ['CANON_CORE_PLANS_OWNER', *_OWNER_EXPORTS]
