from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.canonical_operator_handoff import canonical_operator_resolution


CANON_HEADLESS_OPERATOR_RESOLUTION = True


@dataclass
class FileOperatorResolutionStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def resolve(
        self,
        *,
        run_id: str,
        step_index: int,
        resolution: str,
        note: str = "",
        payload: dict[str, Any] | None = None,
    ) -> Path:
        target = self.root_dir / f"{str(run_id)}_step_{int(step_index):04d}.json"
        data = {
            "run_id": str(run_id),
            "step_index": int(step_index),
            "resolution": str(resolution),
            "note": str(note),
            "payload": dict(payload or {}),
        }
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def read(self, *, run_id: str, step_index: int) -> dict[str, Any]:
        target = self.root_dir / f"{str(run_id)}_step_{int(step_index):04d}.json"
        return json.loads(target.read_text(encoding="utf-8"))

    def exists(self, *, run_id: str, step_index: int) -> bool:
        return (self.root_dir / f"{str(run_id)}_step_{int(step_index):04d}.json").exists()


@dataclass(frozen=True)
class OperatorResolutionLoop:
    """
    Applies an operator resolution to an already-created handoff record.

    Governance only. Never affects the primary execution path.
    """

    resolution_store: FileOperatorResolutionStore

    def apply(
        self,
        *,
        handoff_record: dict[str, Any],
        resolution: str,
        note: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = str(handoff_record.get("run_id") or "")
        step_index = int(handoff_record.get("step_index") or 0)
        self.resolution_store.resolve(
            run_id=run_id,
            step_index=step_index,
            resolution=resolution,
            note=note,
            payload=payload,
        )
        return canonical_operator_resolution(
            handoff_record,
            resolution=str(resolution),
            note=str(note),
            payload=dict(payload or {}),
        )


__all__ = [
    "CANON_HEADLESS_OPERATOR_RESOLUTION",
    "FileOperatorResolutionStore",
    "OperatorResolutionLoop",
]
