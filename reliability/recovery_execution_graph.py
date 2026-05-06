from __future__ import annotations

"""Canonical recovery execution graph.

Infra-only topology model for the single canonical execution path.

Important:
- no business decision logic
- no alternative planner
- no second brain
- only recovery-safe topology validation and resume semantics
"""

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from reliability.execution_checkpoint_store import (
    CANON_CHECKPOINT_STAGE_ORDER,
    ExecutionCheckpoint,
)


CANON_RECOVERY_EXECUTION_GRAPH = True

_STAGE_ORDER: tuple[str, ...] = tuple(CANON_CHECKPOINT_STAGE_ORDER)
_STAGE_INDEX: dict[str, int] = {name: index for index, name in enumerate(_STAGE_ORDER)}

_TERMINAL_STAGES: frozenset[str] = frozenset({"completed", "failed"})
_RESTART_FROM_SCRATCH_STAGES: frozenset[str] = frozenset({"request", "world_state"})
_RESUME_FROM_STAGE_STAGES: frozenset[str] = frozenset(
    {
        "decision",
        "executable_action",
        "execution",
        "verification",
        "state_update",
        "evidence",
    }
)

_ALLOWED_NEXT_BY_STAGE: Mapping[str, tuple[str, ...]] = {
    "request": ("world_state", "failed"),
    "world_state": ("decision", "failed"),
    "decision": ("executable_action", "failed"),
    "executable_action": ("execution", "failed"),
    "execution": ("verification", "failed"),
    "verification": ("state_update", "failed"),
    "state_update": ("evidence", "failed"),
    "evidence": ("completed", "failed"),
    "completed": (),
    "failed": (),
}


@dataclass(frozen=True)
class RecoveryExecutionNode:
    stage: str
    index: int
    is_terminal: bool = False


@dataclass(frozen=True)
class RecoveryExecutionEdge:
    from_stage: str
    to_stage: str


@dataclass(frozen=True)
class RecoveryResumePoint:
    """Recovery-safe resume semantics.

    action:
        - restart_from_scratch
        - resume_execution
        - terminal_noop
        - quarantine
    """

    action: str
    stage: str | None
    reason: str


@dataclass(frozen=True)
class RecoveryGraphValidationReport:
    is_valid: bool
    latest_stage: str | None
    traversed_stages: tuple[str, ...] = field(default_factory=tuple)
    anomalies: tuple[str, ...] = field(default_factory=tuple)
    inferred_entry_stage: str | None = None
    skipped_forward_stages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def can_resume(self) -> bool:
        return self.is_valid and self.latest_stage not in _TERMINAL_STAGES


@dataclass(frozen=True)
class RecoveryExecutionGraph:
    nodes: tuple[RecoveryExecutionNode, ...]
    edges: tuple[RecoveryExecutionEdge, ...]

    def has_stage(self, stage: str) -> bool:
        return str(stage) in _STAGE_INDEX

    def require_stage(self, stage: str) -> str:
        value = str(stage or "").strip()
        if value not in _STAGE_INDEX:
            raise ValueError(f"unknown recovery stage: {value}")
        return value

    def index_of(self, stage: str) -> int:
        return _STAGE_INDEX[self.require_stage(stage)]

    def is_terminal(self, stage: str) -> bool:
        return self.require_stage(stage) in _TERMINAL_STAGES

    def allowed_next(self, stage: str) -> tuple[str, ...]:
        return tuple(_ALLOWED_NEXT_BY_STAGE[self.require_stage(stage)])

    def previous_stage(self, stage: str) -> str | None:
        current = self.require_stage(stage)
        if current in {"request", "failed"}:
            return None
        if current == "completed":
            return "evidence"
        index = _STAGE_INDEX[current]
        if index <= 0:
            return None
        return _STAGE_ORDER[index - 1]

    def next_forward_stage(self, stage: str) -> str | None:
        current = self.require_stage(stage)
        for candidate in self.allowed_next(current):
            if candidate != "failed":
                return candidate
        return None

    def forward_gap(self, from_stage: str, to_stage: str) -> tuple[str, ...]:
        from_index = self.index_of(from_stage)
        to_index = self.index_of(to_stage)
        if to_index <= from_index + 1:
            return ()
        return tuple(_STAGE_ORDER[from_index + 1 : to_index])

    def safe_resume_point(self, latest_stage: str | None) -> RecoveryResumePoint:
        if latest_stage is None:
            return RecoveryResumePoint(
                action="restart_from_scratch",
                stage="request",
                reason="no_checkpoint",
            )

        current = self.require_stage(latest_stage)

        if current in _TERMINAL_STAGES:
            return RecoveryResumePoint(
                action="terminal_noop",
                stage=current,
                reason=f"terminal_{current}",
            )

        if current in _RESTART_FROM_SCRATCH_STAGES:
            return RecoveryResumePoint(
                action="restart_from_scratch",
                stage="request",
                reason=f"restart_from_{current}",
            )

        if current in _RESUME_FROM_STAGE_STAGES:
            return RecoveryResumePoint(
                action="resume_execution",
                stage=current,
                reason=f"resume_from_{current}",
            )

        return RecoveryResumePoint(
            action="quarantine",
            stage=None,
            reason=f"unknown_resume_semantics:{current}",
        )

    def validate_run(self, checkpoints: Iterable[ExecutionCheckpoint]) -> RecoveryGraphValidationReport:
        anomalies: list[str] = []
        traversed: list[str] = []
        latest_stage: str | None = None
        inferred_entry_stage: str | None = None
        last_sequence_no: int | None = None
        seen_checkpoint_ids: dict[str, ExecutionCheckpoint] = {}
        latest_by_stage: dict[str, int] = {}
        skipped_forward_stages: list[str] = []

        for checkpoint in checkpoints:
            checkpoint.validate()
            stage = self.require_stage(checkpoint.stage)

            prior_checkpoint = seen_checkpoint_ids.get(checkpoint.checkpoint_id)
            if prior_checkpoint is not None:
                same_stage = str(prior_checkpoint.stage) == str(checkpoint.stage)
                same_decision = str(prior_checkpoint.decision_id or '') == str(checkpoint.decision_id or '')
                same_action = str(prior_checkpoint.action_id or '') == str(checkpoint.action_id or '')
                if not (same_stage and same_decision and same_action and checkpoint.sequence_no > prior_checkpoint.sequence_no):
                    anomalies.append("duplicate_checkpoint_id")
            seen_checkpoint_ids[checkpoint.checkpoint_id] = checkpoint

            if last_sequence_no is not None and checkpoint.sequence_no <= last_sequence_no:
                anomalies.append("non_monotonic_sequence")
            last_sequence_no = checkpoint.sequence_no

            if stage in latest_by_stage:
                prior_seq = latest_by_stage[stage]
                if checkpoint.sequence_no == prior_seq:
                    anomalies.append(f"duplicate_stage_sequence:{stage}")

            latest_by_stage[stage] = checkpoint.sequence_no

            if latest_stage is None:
                if stage != "request":
                    inferred_entry_stage = stage
            else:
                if stage != latest_stage:
                    allowed = self.allowed_next(latest_stage)
                    if stage not in allowed:
                        if self.index_of(stage) < self.index_of(latest_stage) and stage != "failed":
                            anomalies.append(f"backward_stage_transition:{latest_stage}->{stage}")
                        else:
                            forward_gap = self.forward_gap(latest_stage, stage)
                            if forward_gap:
                                skipped_forward_stages.extend(forward_gap)
                            anomalies.append(f"illegal_stage_transition:{latest_stage}->{stage}")
                    else:
                        forward_gap = self.forward_gap(latest_stage, stage)
                        if forward_gap:
                            skipped_forward_stages.extend(forward_gap)
                else:
                    anomalies.append(f"duplicate_consecutive_stage:{stage}")

                if latest_stage in _TERMINAL_STAGES:
                    anomalies.append(f"transition_after_terminal:{latest_stage}->{stage}")

            traversed.append(stage)
            latest_stage = stage

        if traversed:
            if traversed.count("completed") > 1:
                anomalies.append("multiple_completed_checkpoints")
            if traversed.count("failed") > 1:
                anomalies.append("multiple_failed_checkpoints")
            if "completed" in traversed and traversed[-1] != "completed":
                anomalies.append("completed_not_last_stage")
            if "failed" in traversed and traversed[-1] != "failed":
                anomalies.append("failed_not_last_stage")

        return RecoveryGraphValidationReport(
            is_valid=not anomalies,
            latest_stage=latest_stage,
            traversed_stages=tuple(traversed),
            anomalies=tuple(dict.fromkeys(anomalies)),
            inferred_entry_stage=inferred_entry_stage,
            skipped_forward_stages=tuple(dict.fromkeys(skipped_forward_stages)),
        )


def build_canonical_recovery_execution_graph() -> RecoveryExecutionGraph:
    nodes = tuple(
        RecoveryExecutionNode(
            stage=stage,
            index=index,
            is_terminal=stage in _TERMINAL_STAGES,
        )
        for index, stage in enumerate(_STAGE_ORDER)
    )
    edges = tuple(
        RecoveryExecutionEdge(from_stage=from_stage, to_stage=to_stage)
        for from_stage, next_stages in _ALLOWED_NEXT_BY_STAGE.items()
        for to_stage in next_stages
    )
    return RecoveryExecutionGraph(nodes=nodes, edges=edges)


__all__ = [
    "CANON_RECOVERY_EXECUTION_GRAPH",
    "RecoveryExecutionEdge",
    "RecoveryExecutionGraph",
    "RecoveryExecutionNode",
    "RecoveryGraphValidationReport",
    "RecoveryResumePoint",
    "build_canonical_recovery_execution_graph",
]
