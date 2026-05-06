from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_RUN_DIFF_BUILDER = True


@dataclass(frozen=True)
class RunDiff:
    left_run_id: str
    right_run_id: str
    changed_fields: tuple[str, ...]
    left_only_events: tuple[str, ...]
    right_only_events: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class RunDiffBuilder:
    """
    Produces a compact diff between two persisted runs.

    Analysis only. Never affects execution.
    """

    def build(self, *, left: dict[str, Any], right: dict[str, Any]) -> RunDiff:
        changed_fields: list[str] = []

        tracked_fields = (
            "completed",
            "stop_reason",
            "steps_count",
        )
        for field in tracked_fields:
            if left.get(field) != right.get(field):
                changed_fields.append(field)

        left_feedback = dict(left.get("final_feedback") or {})
        right_feedback = dict(right.get("final_feedback") or {})
        tracked_feedback_fields = (
            "goal_score",
            "goal_reached",
        )
        for field in tracked_feedback_fields:
            if left_feedback.get(field) != right_feedback.get(field):
                changed_fields.append(f"final_feedback.{field}")

        left_events = set(self._event_types(left))
        right_events = set(self._event_types(right))

        left_only = tuple(sorted(left_events - right_events))
        right_only = tuple(sorted(right_events - left_events))

        summary = (
            f"run diff {left.get('run_id')} -> {right.get('run_id')}: "
            f"changed_fields={len(changed_fields)}, "
            f"left_only_events={len(left_only)}, "
            f"right_only_events={len(right_only)}"
        )

        return RunDiff(
            left_run_id=str(left.get("run_id") or ""),
            right_run_id=str(right.get("run_id") or ""),
            changed_fields=tuple(changed_fields),
            left_only_events=left_only,
            right_only_events=right_only,
            summary=summary,
        )

    @staticmethod
    def _event_types(record: dict[str, Any]) -> list[str]:
        trace = dict(record.get("trace") or {})
        events = list(trace.get("events") or [])
        return [str(event.get("event_type") or "") for event in events]


__all__ = [
    "CANON_HEADLESS_RUN_DIFF_BUILDER",
    "RunDiff",
    "RunDiffBuilder",
]
