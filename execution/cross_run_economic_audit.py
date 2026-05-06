from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_CROSS_RUN_ECONOMIC_AUDIT = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True, slots=True)
class CrossRunEconomicAudit:
    total_feedback_events: int
    verified_feedback_events: int
    unique_channels: int
    total_realized_revenue: float
    total_approved_budget: float
    total_requested_budget: float
    snapshot_count: int
    duplicate_feedback_events: int
    duplicate_roi_events: int
    restart_resume_consistent: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_feedback_events': int(self.total_feedback_events),
            'verified_feedback_events': int(self.verified_feedback_events),
            'unique_channels': int(self.unique_channels),
            'total_realized_revenue': float(self.total_realized_revenue),
            'total_approved_budget': float(self.total_approved_budget),
            'total_requested_budget': float(self.total_requested_budget),
            'snapshot_count': int(self.snapshot_count),
            'duplicate_feedback_events': int(self.duplicate_feedback_events),
            'duplicate_roi_events': int(self.duplicate_roi_events),
            'restart_resume_consistent': bool(self.restart_resume_consistent),
            'metadata': dict(self.metadata),
        }


class CrossRunEconomicAuditBuilder:
    """
    Replay-safe cross-run audit aggregator.

    Important:
    - Does not decide.
    - Does not compute new policy.
    - Only audits persisted outputs from the canonical economic path.
    """

    def build(
        self,
        *,
        feedback_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        roi_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        snapshot_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> CrossRunEconomicAudit:
        normalized_feedback = [_safe_dict(row) for row in feedback_rows]
        normalized_roi = [_safe_dict(row) for row in roi_rows]
        normalized_snapshots = [_safe_dict(row) for row in snapshot_rows]

        feedback_ids = [str(row.get('event_id') or row.get('memory_key') or '') for row in normalized_feedback if row]
        roi_ids = [str(row.get('event_id') or '') for row in normalized_roi if row]
        channel_set = {str(row.get('channel') or 'default') for row in normalized_feedback if row}

        duplicate_feedback = max(0, len(feedback_ids) - len({item for item in feedback_ids if item}))
        duplicate_roi = max(0, len(roi_ids) - len({item for item in roi_ids if item}))
        snapshot_ids = {str(row.get('snapshot_id') or '') for row in normalized_snapshots if row}
        restart_resume_consistent = ({item for item in feedback_ids if item} == {item for item in roi_ids if item})

        return CrossRunEconomicAudit(
            total_feedback_events=len(normalized_feedback),
            verified_feedback_events=sum(1 for row in normalized_feedback if _safe_bool(row.get('verified'))),
            unique_channels=len(channel_set),
            total_realized_revenue=sum(_safe_float(row.get('realized_revenue')) for row in normalized_feedback),
            total_approved_budget=sum(_safe_float(row.get('approved_budget')) for row in normalized_feedback),
            total_requested_budget=sum(_safe_float(row.get('requested_budget')) for row in normalized_feedback),
            snapshot_count=len({item for item in snapshot_ids if item}) or len(normalized_snapshots),
            duplicate_feedback_events=duplicate_feedback,
            duplicate_roi_events=duplicate_roi,
            restart_resume_consistent=restart_resume_consistent,
            metadata={
                'owner': 'execution.cross_run_economic_audit',
                'feedback_event_ids': sorted({item for item in feedback_ids if item}),
                'roi_event_ids': sorted({item for item in roi_ids if item}),
                'snapshot_ids': sorted({item for item in snapshot_ids if item}),
            },
        )


__all__ = [
    'CANON_CROSS_RUN_ECONOMIC_AUDIT',
    'CrossRunEconomicAudit',
    'CrossRunEconomicAuditBuilder',
]
