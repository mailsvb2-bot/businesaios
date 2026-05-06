from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.canonical_governance_timeline import canonical_governance_timeline

CANON_DRIFT_HISTORY_JOINER = True

@dataclass(frozen=True)
class DriftHistoryJoiner:
    def build(self, *, baseline_name: str, history_rows: list[dict[str, Any]], rollback_record: dict[str, Any] | None, drift_reports: list[dict[str, Any]]) -> dict[str, Any]:
        return canonical_governance_timeline(
            baseline_name=baseline_name,
            baseline_snapshot=None,
            history_rows=list(history_rows),
            rollback_record=None if rollback_record is None else dict(rollback_record),
            drift_reports=list(drift_reports),
        )

__all__ = ['CANON_DRIFT_HISTORY_JOINER', 'DriftHistoryJoiner']
