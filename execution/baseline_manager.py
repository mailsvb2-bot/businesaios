from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.baseline_history import FileBaselineHistoryStore
from execution.canonical_governance_timeline import canonical_baseline_snapshot


CANON_HEADLESS_BASELINE_MANAGER = True


@dataclass(frozen=True)
class BaselineRecord:
    baseline_name: str
    source_run_id: str
    goal: str
    business_id: str
    tenant_id: str
    promoted_at_label: str
    payload: dict[str, Any]


@dataclass
class FileBaselineStore:
    root_dir: Path
    history_store: FileBaselineHistoryStore | None = None

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def promote(
        self,
        *,
        baseline_name: str,
        record: dict[str, Any],
        promoted_at_label: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        target = self.root_dir / f"{str(baseline_name)}.json"
        existing = None
        if target.exists():
            existing = json.loads(target.read_text(encoding='utf-8'))
        payload = canonical_baseline_snapshot(
            baseline_name=str(baseline_name),
            source_run_id=str(record.get('run_id') or ''),
            promoted_at_label=str(promoted_at_label),
            record=dict(record),
            metadata=dict(metadata or {}),
            existing_payload=existing,
        )
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        if self.history_store is not None:
            self.history_store.append(
                baseline_name=baseline_name,
                event_type="promoted",
                source_run_id=str(record.get("run_id") or ""),
                payload={
                    "promoted_at_label": str(promoted_at_label),
                    "metadata": dict(metadata or {}),
                },
            )
        return target

    def read(self, *, baseline_name: str) -> dict[str, Any]:
        target = self.root_dir / f"{str(baseline_name)}.json"
        payload = json.loads(target.read_text(encoding='utf-8'))
        return canonical_baseline_snapshot(
            baseline_name=str(payload.get('baseline_name') or baseline_name),
            source_run_id=str(payload.get('source_run_id') or ''),
            promoted_at_label=str(payload.get('promoted_at_label') or ''),
            record=dict(payload.get('record') or {}),
            metadata=dict(payload.get('metadata') or {}),
            existing_payload=payload,
        )

    def exists(self, *, baseline_name: str) -> bool:
        return (self.root_dir / f"{str(baseline_name)}.json").exists()

    def list_names(self) -> list[str]:
        return sorted(path.stem for path in self.root_dir.glob("*.json"))


__all__ = [
    "CANON_HEADLESS_BASELINE_MANAGER",
    "BaselineRecord",
    "FileBaselineStore",
]
