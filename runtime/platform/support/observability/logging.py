from __future__ import annotations

from observability.logger import CANON_OBSERVABILITY_LOGGER, get_logger, log_kv

CANON_RUNTIME_SUPPORT_OBSERVABILITY_LOGGING = True

__all__ = [
    "CANON_OBSERVABILITY_LOGGER",
    "CANON_RUNTIME_SUPPORT_OBSERVABILITY_LOGGING",
    "get_logger",
    "log_kv",
]


def __getattr__(name: str):
    if name in __all__:
        return globals()[name]
    raise AttributeError(name)
