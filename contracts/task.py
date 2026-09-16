from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_DURABLE_TASK_CONTRACT = True


class DurableTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class DurableTask:
    task_id: str
    tenant_id: str
    business_id: str
    title: str | None = None
    status: DurableTaskStatus = DurableTaskStatus.PENDING
    created_at_ms: int = 0
    updated_at_ms: int = 0
    terminal_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("task_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "title", _optional(self.title, "title"))
        object.__setattr__(self, "status", DurableTaskStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("task timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        terminal_states = {DurableTaskStatus.COMPLETED, DurableTaskStatus.FAILED, DurableTaskStatus.CANCELLED}
        if self.terminal_at_ms is not None:
            terminal = int(self.terminal_at_ms)
            if terminal < created:
                raise ValueError("terminal_at_ms must be >= created_at_ms")
            object.__setattr__(self, "terminal_at_ms", terminal)
        if self.status in terminal_states and self.terminal_at_ms is None:
            raise ValueError("terminal task requires terminal_at_ms")
        if self.status not in terminal_states and self.terminal_at_ms is not None:
            raise ValueError("non-terminal task cannot have terminal_at_ms")


class DurableTaskNotFound(LookupError):
    pass


__all__ = ["CANON_DURABLE_TASK_CONTRACT", "DurableTask", "DurableTaskNotFound", "DurableTaskStatus"]
