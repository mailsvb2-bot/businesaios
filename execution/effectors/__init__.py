"""Canonical effector owner surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_EFFECTOR_PACKAGE_OWNER = True
_OWNER_MAP = {
    'CANON_EFFECTOR_BASE': ('execution.effectors.base', 'CANON_EFFECTOR_BASE'),
    'ConnectorEffectorBase': ('execution.effectors.base', 'ConnectorEffectorBase'),
    'EffectorBase': ('execution.effectors.base', 'EffectorBase'),
    'CANON_EFFECTOR_RESULT': ('execution.effectors.result', 'CANON_EFFECTOR_RESULT'),
    'EffectorResult': ('execution.effectors.result', 'EffectorResult'),
    'CANON_EFFECTOR_ROUTER': ('execution.effectors.router', 'CANON_EFFECTOR_ROUTER'),
    'EffectorRouter': ('execution.effectors.router', 'EffectorRouter'),
    'CANON_EFFECTOR_CATALOG': ('execution.effectors.catalog', 'CANON_EFFECTOR_CATALOG'),
    'build_effector': ('execution.effectors.catalog', 'build_effector'),
}

def __getattr__(name: str) -> Any:
    if name == 'CANON_EFFECTOR_PACKAGE_OWNER':
        return CANON_EFFECTOR_PACKAGE_OWNER
    target = _OWNER_MAP.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = ['CANON_EFFECTOR_PACKAGE_OWNER', *_OWNER_MAP.keys()]
