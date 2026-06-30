"""Canonical constructor-call discipline for outbound queue boot wiring."""

from __future__ import annotations

import importlib
from typing import Any
from collections.abc import Callable

CANON_BOOT_WIRING_ONLY = True
CANON_OUTBOUND_CONSTRUCTOR_CALL = True

def build_with_supported_kwargs(*, constructor: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    accepted_kwargs = importlib.import_module("core.utils.call_signature").accepted_kwargs
    supported = accepted_kwargs(constructor, dict(kwargs))
    return constructor(**supported)


__all__ = ['CANON_BOOT_WIRING_ONLY', 'CANON_OUTBOUND_CONSTRUCTOR_CALL', 'build_with_supported_kwargs']
