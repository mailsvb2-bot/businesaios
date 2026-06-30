"""Helpers for thin decision transition surfaces.

These helpers keep historical ``core.decision.*`` imports alive without
recreating owner logic in this namespace. Every transition module should bind to a
single canonical owner module and expose only lazy attribute delegation.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from types import ModuleType

CANON_CORE_DECISION_TRANSITION_HELPER = True

def install_transition_module(
    *,
    globals_dict: dict[str, object],
    canonical_owner_module: str,
    extra_exports: Iterable[str] = (),
) -> ModuleType:
    target = importlib.import_module(canonical_owner_module)
    globals_dict['CANON_TRANSITION_SURFACE'] = True
    globals_dict['CANONICAL_OWNER_MODULE'] = canonical_owner_module
    globals_dict['_TARGET_MODULE'] = target

    def __getattr__(name: str):
        return getattr(target, name)

    def __dir__() -> list[str]:
        return sorted(set(globals_dict) | set(dir(target)))

    exports = {
        name for name in dir(target)
        if not name.startswith('_')
    }
    exports.update(extra_exports)
    exports.update({'CANON_TRANSITION_SURFACE', 'CANONICAL_OWNER_MODULE'})
    globals_dict['__getattr__'] = __getattr__
    globals_dict['__dir__'] = __dir__
    globals_dict['__all__'] = sorted(exports)
    return target


__all__ = ['CANON_CORE_DECISION_TRANSITION_HELPER', 'install_transition_module']
