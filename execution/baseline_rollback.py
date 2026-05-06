from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.baseline_history import FileBaselineHistoryStore
from execution.canonical_governance_timeline import canonical_rollback_record


CANON_HEADLESS_BASELINE_ROLLBACK = True


@dataclass
class FileBaselineRollbackStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def record_rollback(
        self,
        *,
        baseline_name: str,
        previous_source_run_id: str,
        new_source_run_id: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        target = self.root_dir / f"{str(baseline_name)}.json"
        existing = None
        if target.exists():
            existing = json.loads(target.read_text(encoding='utf-8'))
        payload = canonical_rollback_record(
            baseline_name=str(baseline_name),
            previous_source_run_id=str(previous_source_run_id),
            new_source_run_id=str(new_source_run_id),
            reason=str(reason),
            metadata=dict(metadata or {}),
            existing_payload=existing,
        )
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def read(self, *, baseline_name: str) -> dict[str, Any]:
        target = self.root_dir / f"{str(baseline_name)}.json"
        payload = json.loads(target.read_text(encoding='utf-8'))
        return canonical_rollback_record(
            baseline_name=str(payload.get('baseline_name') or baseline_name),
            previous_source_run_id=str(payload.get('previous_source_run_id') or ''),
            new_source_run_id=str(payload.get('new_source_run_id') or ''),
            reason=str(payload.get('reason') or ''),
            metadata=dict(payload.get('metadata') or {}),
            existing_payload=payload,
        )


@dataclass(frozen=True)
class BaselineRollbackManager:
    rollback_store: FileBaselineRollbackStore
    history_store: FileBaselineHistoryStore | None = None

    def rollback(
        self,
        *,
        baseline_store: Any,
        baseline_name: str,
        fallback_record: dict[str, Any],
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = baseline_store.read(baseline_name=baseline_name)
        previous_run_id = str(current.get("source_run_id") or "")
        baseline_store.promote(
            baseline_name=baseline_name,
            record=fallback_record,
            promoted_at_label="rollback",
            metadata={"rollback_reason": str(reason), **dict(metadata or {})},
        )
        self.rollback_store.record_rollback(
            baseline_name=baseline_name,
            previous_source_run_id=previous_run_id,
            new_source_run_id=str(fallback_record.get("run_id") or ""),
            reason=str(reason),
            metadata=dict(metadata or {}),
        )
        if self.history_store is not None:
            self.history_store.append(
                baseline_name=baseline_name,
                event_type="rolled_back",
                source_run_id=str(fallback_record.get("run_id") or ""),
                payload={
                    "previous_source_run_id": previous_run_id,
                    "reason": str(reason),
                    "metadata": dict(metadata or {}),
                },
            )
        return baseline_store.read(baseline_name=baseline_name)


__all__ = [
    "CANON_HEADLESS_BASELINE_ROLLBACK",
    "BaselineRollbackManager",
    "FileBaselineRollbackStore",
]
