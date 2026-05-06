from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_ROLLBACK_AUDIT_TIMELINE = True


@dataclass(frozen=True)
class RollbackAuditTimelineBuilder:
    """
    Builds a readable rollback timeline from rollback records and baseline history.

    Reporting only. Never affects execution.
    """

    def build(
        self,
        *,
        baseline_name: str,
        rollback_record: dict[str, Any],
        history_rows: list[dict[str, Any]],
    ) -> str:
        lines = [f"Baseline rollback timeline: {baseline_name}"]
        lines.append(
            "Rollback: "
            f"{rollback_record.get('previous_source_run_id')} -> {rollback_record.get('new_source_run_id')}"
        )
        lines.append(f"Reason: {rollback_record.get('reason')}")
        lines.append("History:")
        for row in history_rows:
            lines.append(
                f"- {row.get('event_type')} run={row.get('source_run_id')} "
                f"payload={row.get('payload')}"
            )
        return "\n".join(lines)


__all__ = [
    "CANON_HEADLESS_ROLLBACK_AUDIT_TIMELINE",
    "RollbackAuditTimelineBuilder",
]
