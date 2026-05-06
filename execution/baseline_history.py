from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.canonical_governance_timeline import canonical_governance_history_row


CANON_HEADLESS_BASELINE_HISTORY = True


@dataclass
class FileBaselineHistoryStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        baseline_name: str,
        event_type: str,
        source_run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Path:
        target = self.root_dir / f"{str(baseline_name)}.jsonl"
        row = canonical_governance_history_row(
            baseline_name=str(baseline_name),
            event_type=str(event_type),
            source_run_id=str(source_run_id),
            payload=dict(payload or {}),
        )
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return target

    def read_all(self, *, baseline_name: str) -> list[dict[str, Any]]:
        target = self.root_dir / f"{str(baseline_name)}.jsonl"
        if not target.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                rows.append(canonical_governance_history_row(
                    baseline_name=str(payload.get('baseline_name') or baseline_name),
                    event_type=str(payload.get('event_type') or ''),
                    source_run_id=str(payload.get('source_run_id') or ''),
                    payload=dict(payload.get('payload') or {}),
                ))
        return rows


__all__ = [
    "CANON_HEADLESS_BASELINE_HISTORY",
    "FileBaselineHistoryStore",
]
