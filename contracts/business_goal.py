from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BUSINESS_GOAL_SCHEMA_VERSION = 1
CANON_BUSINESS_GOAL_CONTRACT = True


class GoalLifecycleStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class BusinessGoal:
    """PII-free canonical business Goal identity, hierarchy and lifecycle."""

    goal_id: str
    tenant_id: str
    business_id: str
    goal_kind: str
    target_key: str | None = None
    parent_goal_id: str | None = None
    priority: int = 50
    schema_version: int = BUSINESS_GOAL_SCHEMA_VERSION
    lifecycle_status: GoalLifecycleStatus = GoalLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    terminal_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("goal_id", "tenant_id", "business_id", "goal_kind"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "target_key", _optional(self.target_key, "target_key"))
        object.__setattr__(self, "parent_goal_id", _optional(self.parent_goal_id, "parent_goal_id"))
        if self.parent_goal_id == self.goal_id:
            raise ValueError("goal cannot be its own parent")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int) or not 0 <= self.priority <= 100:
            raise ValueError("priority must be an integer from 0 to 100")
        if isinstance(self.schema_version, bool) or int(self.schema_version) != BUSINESS_GOAL_SCHEMA_VERSION:
            raise ValueError(f"unsupported business goal schema_version: {self.schema_version}")
        object.__setattr__(self, "schema_version", BUSINESS_GOAL_SCHEMA_VERSION)
        object.__setattr__(self, "lifecycle_status", GoalLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("business goal timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        terminal = self.terminal_at_ms
        if terminal is not None:
            terminal = int(terminal)
            if terminal < created:
                raise ValueError("terminal_at_ms must be >= created_at_ms")
            object.__setattr__(self, "terminal_at_ms", terminal)
        if self.lifecycle_status is GoalLifecycleStatus.ACTIVE and terminal is not None:
            raise ValueError("active goal cannot have terminal_at_ms")
        if self.lifecycle_status is not GoalLifecycleStatus.ACTIVE and terminal is None:
            raise ValueError("terminal goal requires terminal_at_ms")


class BusinessGoalNotFound(LookupError):
    pass


__all__ = [
    "BUSINESS_GOAL_SCHEMA_VERSION",
    "CANON_BUSINESS_GOAL_CONTRACT",
    "BusinessGoal",
    "BusinessGoalNotFound",
    "GoalLifecycleStatus",
]
