from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_DURABLE_TASK_CONTRACT = True


class DurableTaskStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"

    # Backward-compatible symbolic aliases. New durable state always projects
    # to the canonical Phase 9 vocabulary above.
    PENDING = CREATED
    COMPLETED = SUCCEEDED

    @classmethod
    def _missing_(cls, value: object):
        legacy = {
            "pending": cls.CREATED,
            "completed": cls.SUCCEEDED,
        }
        return legacy.get(str(value or "").strip().lower())


class WaitConditionKind(StrEnum):
    HUMAN = "human"
    WEBHOOK = "webhook"
    CLIENT = "client"
    PAYMENT = "payment"
    DATE = "date"
    APPROVAL = "approval"
    PROVIDER_RECOVERY = "provider_recovery"


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
class WaitCondition:
    condition_id: str
    kind: WaitConditionKind
    correlation_key: str | None = None
    resume_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition_id", _required(self.condition_id, "condition_id"))
        object.__setattr__(self, "kind", WaitConditionKind(self.kind))
        object.__setattr__(
            self,
            "correlation_key",
            _optional(self.correlation_key, "correlation_key"),
        )
        if self.resume_at_ms is not None:
            resume_at_ms = int(self.resume_at_ms)
            if resume_at_ms < 0:
                raise ValueError("resume_at_ms cannot be negative")
            object.__setattr__(self, "resume_at_ms", resume_at_ms)
        if self.kind is WaitConditionKind.DATE and self.resume_at_ms is None:
            raise ValueError("date wait condition requires resume_at_ms")

    def to_dict(self) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "kind": self.kind.value,
            "correlation_key": self.correlation_key,
            "resume_at_ms": self.resume_at_ms,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> WaitCondition:
        return cls(
            condition_id=str(payload.get("condition_id") or ""),
            kind=WaitConditionKind(str(payload.get("kind") or "")),
            correlation_key=(
                None
                if payload.get("correlation_key") is None
                else str(payload.get("correlation_key") or "")
            ),
            resume_at_ms=(
                None
                if payload.get("resume_at_ms") is None
                else int(payload.get("resume_at_ms") or 0)
            ),
        )


@dataclass(frozen=True, slots=True)
class DurableTask:
    task_id: str
    tenant_id: str
    business_id: str
    title: str | None = None
    status: DurableTaskStatus = DurableTaskStatus.CREATED
    created_at_ms: int = 0
    updated_at_ms: int = 0
    terminal_at_ms: int | None = None
    version: int = 1
    wait_condition: WaitCondition | None = None

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

        version = int(self.version)
        if version < 1:
            raise ValueError("task version must be >= 1")
        object.__setattr__(self, "version", version)

        wait_condition = self.wait_condition
        if wait_condition is not None and not isinstance(wait_condition, WaitCondition):
            if not isinstance(wait_condition, dict):
                raise ValueError("wait_condition must be WaitCondition or dict")
            wait_condition = WaitCondition.from_dict(wait_condition)
            object.__setattr__(self, "wait_condition", wait_condition)
        if self.status is DurableTaskStatus.WAITING and wait_condition is None:
            raise ValueError("waiting task requires wait_condition")
        if self.status is not DurableTaskStatus.WAITING and wait_condition is not None:
            raise ValueError("only waiting task can have wait_condition")

        terminal_states = {
            DurableTaskStatus.SUCCEEDED,
            DurableTaskStatus.FAILED,
            DurableTaskStatus.CANCELLED,
        }
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


__all__ = [
    "CANON_DURABLE_TASK_CONTRACT",
    "DurableTask",
    "DurableTaskNotFound",
    "DurableTaskStatus",
    "WaitCondition",
    "WaitConditionKind",
]