from __future__ import annotations

from enum import Enum


class LifecycleState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    BLOCKED = "blocked"
    ARCHIVED = "archived"

__all__ = [
    "LifecycleState",
]
