from __future__ import annotations

"""Canonical runtime exception-observability surface.

Runtime best-effort paths should depend on this adapter instead of reaching into
core observability internals directly.
"""

import importlib

CANON_RUNTIME_ERROR_OBSERVABILITY_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_ERROR_OBSERVABILITY_PUBLIC_API',
    'exception_throttled',
    'swallow',
    'warning_throttled',
]


def __getattr__(name: str):
    if name == 'swallow':
        return getattr(importlib.import_module('core.observability.silent'), name)
    if name in {'exception_throttled', 'warning_throttled'}:
        return getattr(importlib.import_module('core.observability.throttled_logger'), name)
    raise AttributeError(name)
