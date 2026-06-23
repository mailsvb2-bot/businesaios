"""Retention package lazy public surface.

The package root must stay safe to import from anywhere. Heavy engine wiring
is loaded lazily through __getattr__.
"""

from __future__ import annotations

from typing import Any

__all__ = ["RetentionEngine"]

def __getattr__(name: str) -> Any:
    if name != "RetentionEngine":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from core.retention.engine import RetentionEngine
    globals()[name] = RetentionEngine
    return RetentionEngine
