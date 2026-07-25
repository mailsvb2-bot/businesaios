from __future__ import annotations

"""Immutable facts and passive helpers for canonical recovery reconstruction."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from reliability.execution_checkpoint_store import ExecutionCheckpoint
from reliability.execution_reconciliation import ReconciliationReport
from reliability.idempotency_contract import IdempotencyRecord, IdempotencyState
from reliability.outbox_store import OutboxMessage, OutboxState
from reliability.recovery_execution_graph import (
    RecoveryGraphValidationReport,
    RecoveryResumePoint,
)

CANON_RECOVERY_RUN_REBUILDER = True

_LATE_IDEMPOTENCY_STAGES = frozenset(
    {
        "decision",
        "executable_action",
        "execution",
        "verification",
        "state_update",
        "evidence",
        "completed",
        "failed",
    }
)
_LATE_LEASE_STAGES = frozenset(
    {"execution", "verification", "state_update", "evidence"}
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return value


def _require_run_id(value: object) -> str:
    run_id = str(value or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    return run_id


def _optional_id(value: object | None, name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} must not be blank when provided")
    return normalized


def _checkpoint_ids(
    checkpoints: tuple[ExecutionCheckpoint, ...],
    attribute: str,
) -> frozenset[str]:
    values: set[str] = set()
    for checkpoint in checkpoints:
        raw = getattr(checkpoint, attribute)
        if raw is not None and str(raw).strip():
            values.add(str(raw).strip())
    return frozenset(values)


def _single(values: frozenset[str]) -> str | None:
    return next(iter(values)) if len(values) == 1 else None


@dataclass(frozen=True)
class _RecoverySnapshot:
    checkpoints: tuple[ExecutionCheckpoint, ...]
    idempotency_record: IdempotencyRecord | None
    outbox_message: OutboxMessage | None
    outbox_ids: frozenset[str]
    idempotency_keys: frozenset[str]
    trace_ids: frozenset[str]
    decision_ids: frozenset[str]
    canonical_outbox_id: str | None
    canonical_idempotency_key: str | None
    resolved_outbox_id: str | None


@dataclass(frozen=True)
class RebuiltRunFacts:
    tenant_id: str
    run_id: str
    latest_stage: str | None
    latest_checkpoint: ExecutionCheckpoint | None
    checkpoints: tuple[ExecutionCheckpoint, ...] = field(default_factory=tuple)
    idempotency_record: IdempotencyRecord | None = None
    outbox_message: OutboxMessage | None = None
    graph_validation: RecoveryGraphValidationReport = field(
        default_factory=lambda: RecoveryGraphValidationReport(
            is_valid=True,
            latest_stage=None,
        )
    )
    reconciliation: ReconciliationReport = field(
        default_factory=lambda: ReconciliationReport(
            run_id="",
            latest_stage=None,
            idempotency_state=None,
            outbox_state=None,
            checkpoint_count=0,
            anomalies=(),
        )
    )
    resume_point: RecoveryResumePoint = field(
        default_factory=lambda: RecoveryResumePoint(
            action="restart_from_scratch",
            stage="request",
            reason="default",
        )
    )
    anomalies: tuple[str, ...] = field(default_factory=tuple)
    derived_flags: Mapping[str, Any] = field(default_factory=dict)
    canonical_outbox_message_id: str | None = None
    canonical_idempotency_key: str | None = None
    partial_history_detected: bool = False
    observed_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        object.__setattr__(self, "run_id", _require_run_id(self.run_id))
        object.__setattr__(self, "checkpoints", tuple(self.checkpoints))
        object.__setattr__(
            self,
            "anomalies",
            tuple(dict.fromkeys(str(item) for item in self.anomalies)),
        )
        object.__setattr__(
            self,
            "derived_flags",
            MappingProxyType(dict(self.derived_flags)),
        )
        object.__setattr__(self, "observed_at", _require_aware(self.observed_at))

    @property
    def checkpoint_count(self) -> int:
        return len(self.checkpoints)

    @property
    def is_terminal(self) -> bool:
        return self.latest_stage in {"completed", "failed"}

    @property
    def is_clean(self) -> bool:
        return not self.anomalies

    @property
    def idempotency_state(self) -> str | None:
        record = self.idempotency_record
        return None if record is None else record.state.value

    @property
    def outbox_state(self) -> str | None:
        message = self.outbox_message
        return None if message is None else message.state.value

    @property
    def has_live_idempotency_lease(self) -> bool:
        record = self.idempotency_record
        return bool(
            record is not None
            and record.state is IdempotencyState.IN_PROGRESS
            and record.has_live_lease(now=self.observed_at)
        )

    @property
    def idempotency_is_terminal(self) -> bool:
        record = self.idempotency_record
        return bool(
            record is not None
            and record.state
            in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
        )

    @property
    def outbox_is_claimable(self) -> bool:
        message = self.outbox_message
        return bool(
            message is not None
            and message.is_claimable(now=self.observed_at)
        )

    @property
    def outbox_is_delivered(self) -> bool:
        message = self.outbox_message
        return bool(
            message is not None and message.state is OutboxState.DELIVERED
        )

    @property
    def outbox_is_dead(self) -> bool:
        message = self.outbox_message
        return bool(message is not None and message.state is OutboxState.DEAD)



__all__ = [
    "CANON_RECOVERY_RUN_REBUILDER",
    "RebuiltRunFacts",
]
