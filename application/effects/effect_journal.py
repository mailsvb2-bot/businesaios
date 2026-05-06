from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANON_HEADLESS_EFFECT_JOURNAL = True


@dataclass
class FileEffectJournal:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        run_id: str,
        step_index: int,
        decision_id: str,
        action: str,
        effect: dict[str, Any],
    ) -> Path:
        target = self.root_dir / f"{str(run_id)}.jsonl"
        line = {
            "run_id": str(run_id),
            "step_index": int(step_index),
            "decision_id": str(decision_id),
            "action": str(action),
            "effect": dict(effect or {}),
        }
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return target

    def read_all(self, *, run_id: str) -> list[dict[str, Any]]:
        target = self.root_dir / f"{str(run_id)}.jsonl"
        if not target.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


__all__ = [
    "CANON_HEADLESS_EFFECT_JOURNAL",
    "FileEffectJournal",
]
