from __future__ import annotations

"""Canonical offers package root with legacy alias support."""

import sys
from importlib import import_module

CANON_TRANSITION_SURFACE = True
CANON_COMPAT_SHIM = True
CANON_OFFERS_PACKAGE_ALIAS_OWNER = True

_COMPAT_ALIAS_MAP = {
    "offer_engine": "core.offers.engine",
}


def _install_offer_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        target_module = import_module(target_module_name)
        qualified_name = f"{__name__}.{alias_name}"
        sys.modules[qualified_name] = target_module
        setattr(package, alias_name, target_module)


_install_offer_aliases()

__all__ = [
    "CANON_TRANSITION_SURFACE",
    "CANON_COMPAT_SHIM",
    "CANON_OFFERS_PACKAGE_ALIAS_OWNER",
]
