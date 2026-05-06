from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANON_HEADLESS_STATE_STORE = True


@dataclass
class FileHeadlessStateStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        *,
        run_id: str,
        step_index: int,
        phase: str,
        snapshot: dict[str, Any],
    ) -> Path:
        run_dir = self.root_dir / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        safe_phase = str(phase).strip().replace("/", "_").replace("\\", "_") or "snapshot"
        target = run_dir / f"step_{int(step_index):04d}_{safe_phase}.json"
        target.write_text(
            json.dumps(dict(snapshot or {}), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return target

    def load_latest_snapshot(self, *, run_id: str) -> dict[str, Any]:
        run_dir = self.root_dir / str(run_id)
        if not run_dir.exists():
            return {}
        files = sorted(run_dir.glob("step_*.json"))
        if not files:
            return {}
        return json.loads(files[-1].read_text(encoding="utf-8"))


__all__ = [
    "CANON_HEADLESS_STATE_STORE",
    "FileHeadlessStateStore",
]
