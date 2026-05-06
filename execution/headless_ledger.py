from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from execution.canonical_persistence_vocabulary import canonical_run_persistence_vocabulary


CANON_HEADLESS_LEDGER = True


@dataclass(frozen=True)
class LedgerRecord:
    run_id: str
    trace_id: str
    business_id: str
    tenant_id: str
    goal: str
    completed: bool
    stop_reason: str
    steps_count: int
    final_feedback: dict[str, Any]
    trace: dict[str, Any]
    canonical_run_artifact: dict[str, Any] = field(default_factory=dict)
    canonical_persistence_vocabulary: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileHeadlessLedger:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def write(self, record: LedgerRecord) -> Path:
        target = self.root_dir / f"{record.run_id}.json"
        payload = {
            "run_id": record.run_id,
            "trace_id": record.trace_id,
            "business_id": record.business_id,
            "tenant_id": record.tenant_id,
            "goal": record.goal,
            "completed": bool(record.completed),
            "stop_reason": record.stop_reason,
            "steps_count": int(record.steps_count),
            "final_feedback": dict(record.final_feedback),
            "trace": dict(record.trace),
            "canonical_run_artifact": dict(record.canonical_run_artifact),
            "canonical_persistence_vocabulary": dict(record.canonical_persistence_vocabulary) or canonical_run_persistence_vocabulary({
                "run_id": record.run_id,
                "trace_id": record.trace_id,
                "business_id": record.business_id,
                "tenant_id": record.tenant_id,
                "goal": record.goal,
                "completed": bool(record.completed),
                "stop_reason": record.stop_reason,
                "steps_count": int(record.steps_count),
                "final_feedback": dict(record.final_feedback),
                "canonical_run_artifact": dict(record.canonical_run_artifact),
            }),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def read(self, run_id: str) -> dict[str, Any]:
        target = self.root_dir / f"{run_id}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload.get('canonical_persistence_vocabulary'), dict):
            payload['canonical_persistence_vocabulary'] = canonical_run_persistence_vocabulary(payload)
        return payload

    def exists(self, run_id: str) -> bool:
        return (self.root_dir / f"{run_id}.json").exists()


__all__ = [
    "CANON_HEADLESS_LEDGER",
    "FileHeadlessLedger",
    "LedgerRecord",
]
