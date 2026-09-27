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


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    initial_backoff_ms: int = 0
    max_backoff_ms: int = 0
    retryable_statuses: tuple[str, ...] = ("recoverable", "temporary_failure", "rate_limited")
    retry_ambiguous: bool = False

    def __post_init__(self) -> None:
        max_attempts = int(self.max_attempts)
        initial_backoff_ms = int(self.initial_backoff_ms)
        max_backoff_ms = int(self.max_backoff_ms)
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if initial_backoff_ms < 0 or max_backoff_ms < 0:
            raise ValueError("retry backoff cannot be negative")
        if max_backoff_ms and max_backoff_ms < initial_backoff_ms:
            raise ValueError("max_backoff_ms must be >= initial_backoff_ms")
        statuses = tuple(dict.fromkeys(_required(value, "retryable_status", 100) for value in self.retryable_statuses))
        object.__setattr__(self, "max_attempts", max_attempts)
        object.__setattr__(self, "initial_backoff_ms", initial_backoff_ms)
        object.__setattr__(self, "max_backoff_ms", max_backoff_ms)
        object.__setattr__(self, "retryable_statuses", statuses)

    def allows_retry(self, *, attempt: int, status: str, ambiguous: bool = False) -> bool:
        if ambiguous and not self.retry_ambiguous:
            return False
        return 1 <= int(attempt) < self.max_attempts and str(status or "").strip() in self.retryable_statuses

    def backoff_ms(self, *, attempt: int) -> int:
        if int(attempt) < 1:
            raise ValueError("attempt must be >= 1")
        if self.initial_backoff_ms == 0:
            return 0
        delay = self.initial_backoff_ms * (2 ** max(0, int(attempt) - 1))
        return min(delay, self.max_backoff_ms) if self.max_backoff_ms else delay

    def to_dict(self) -> dict[str, object]:
        return {
            "max_attempts": self.max_attempts,
            "initial_backoff_ms": self.initial_backoff_ms,
            "max_backoff_ms": self.max_backoff_ms,
            "retryable_statuses": list(self.retryable_statuses),
            "retry_ambiguous": bool(self.retry_ambiguous),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> RetryPolicy:
        return cls(
            max_attempts=int(payload.get("max_attempts") or 1),
            initial_backoff_ms=int(payload.get("initial_backoff_ms") or 0),
            max_backoff_ms=int(payload.get("max_backoff_ms") or 0),
            retryable_statuses=tuple(
                str(item)
                for item in payload.get(
                    "retryable_statuses",
                    ("recoverable", "temporary_failure", "rate_limited"),
                )
            ),
            retry_ambiguous=bool(payload.get("retry_ambiguous", False)),
        )


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    attempt_timeout_ms: int | None = None
    task_deadline_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("attempt_timeout_ms", "task_deadline_ms"):
            raw = getattr(self, field_name)
            if raw is None:
                continue
            value = int(raw)
            if value <= 0:
                raise ValueError(f"{field_name} must be > 0")
            object.__setattr__(self, field_name, value)

    def attempt_deadline_ms(self, *, started_at_ms: int) -> int | None:
        if self.attempt_timeout_ms is None:
            return None
        return int(started_at_ms) + self.attempt_timeout_ms

    def is_task_timed_out(self, *, now_ms: int) -> bool:
        return self.task_deadline_ms is not None and int(now_ms) >= self.task_deadline_ms

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_timeout_ms": self.attempt_timeout_ms,
            "task_deadline_ms": self.task_deadline_ms,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TimeoutPolicy:
        return cls(
            attempt_timeout_ms=(
                None if payload.get("attempt_timeout_ms") is None else int(payload["attempt_timeout_ms"])
            ),
            task_deadline_ms=(
                None if payload.get("task_deadline_ms") is None else int(payload["task_deadline_ms"])
            ),
        )


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
    artifact_ids: tuple[str, ...] = ()
    retry_policy: RetryPolicy = RetryPolicy()
    timeout_policy: TimeoutPolicy = TimeoutPolicy()

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
        artifact_ids = tuple(
            dict.fromkeys(_required(value, "artifact_id") for value in self.artifact_ids)
        )
        object.__setattr__(self, "artifact_ids", artifact_ids)
        retry_policy = self.retry_policy
        if not isinstance(retry_policy, RetryPolicy):
            if not isinstance(retry_policy, dict):
                raise ValueError("retry_policy must be RetryPolicy or dict")
            retry_policy = RetryPolicy.from_dict(retry_policy)
            object.__setattr__(self, "retry_policy", retry_policy)
        timeout_policy = self.timeout_policy
        if not isinstance(timeout_policy, TimeoutPolicy):
            if not isinstance(timeout_policy, dict):
                raise ValueError("timeout_policy must be TimeoutPolicy or dict")
            timeout_policy = TimeoutPolicy.from_dict(timeout_policy)
            object.__setattr__(self, "timeout_policy", timeout_policy)

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


@dataclass(frozen=True, slots=True)
class DurableTaskRun:
    tenant_id: str
    business_id: str
    task_id: str
    run_id: str
    started_at_ms: int
    updated_at_ms: int
    checkpoint_count: int
    terminal_stage: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("tenant_id", "business_id", "task_id", "run_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        started_at_ms = int(self.started_at_ms)
        updated_at_ms = int(self.updated_at_ms)
        checkpoint_count = int(self.checkpoint_count)
        if started_at_ms < 0 or updated_at_ms < started_at_ms:
            raise ValueError("task run timestamps are invalid")
        if checkpoint_count < 1:
            raise ValueError("checkpoint_count must be >= 1")
        object.__setattr__(self, "started_at_ms", started_at_ms)
        object.__setattr__(self, "updated_at_ms", updated_at_ms)
        object.__setattr__(self, "checkpoint_count", checkpoint_count)
        object.__setattr__(
            self,
            "terminal_stage",
            _optional(self.terminal_stage, "terminal_stage", 100),
        )


@dataclass(frozen=True, slots=True)
class DurableTaskStep:
    tenant_id: str
    business_id: str
    task_id: str
    run_id: str
    step_id: str
    first_sequence_no: int
    last_sequence_no: int
    checkpoint_count: int
    latest_stage: str

    def __post_init__(self) -> None:
        for field_name in ("tenant_id", "business_id", "task_id", "run_id", "step_id", "latest_stage"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        first_sequence_no = int(self.first_sequence_no)
        last_sequence_no = int(self.last_sequence_no)
        checkpoint_count = int(self.checkpoint_count)
        if first_sequence_no < 0 or last_sequence_no < first_sequence_no:
            raise ValueError("task step sequence bounds are invalid")
        if checkpoint_count < 1:
            raise ValueError("checkpoint_count must be >= 1")
        object.__setattr__(self, "first_sequence_no", first_sequence_no)
        object.__setattr__(self, "last_sequence_no", last_sequence_no)
        object.__setattr__(self, "checkpoint_count", checkpoint_count)


class DurableTaskNotFound(LookupError):
    pass


__all__ = [
    "CANON_DURABLE_TASK_CONTRACT",
    "DurableTask",
    "DurableTaskNotFound",
    "DurableTaskRun",
    "DurableTaskStatus",
    "DurableTaskStep",
    "RetryPolicy",
    "TimeoutPolicy",
    "WaitCondition",
    "WaitConditionKind",
]
