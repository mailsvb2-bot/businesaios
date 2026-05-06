from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.canonical_operator_handoff import canonical_operator_handoff


CANON_HEADLESS_OPERATOR_HANDOFF = True


@dataclass
class FileOperatorHandoffStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def write_record(
        self,
        *,
        run_id: str,
        step_index: int,
        payload: dict[str, Any],
    ) -> Path:
        target = self.root_dir / f"{str(run_id)}_step_{int(step_index):04d}.json"
        target.write_text(
            json.dumps(canonical_operator_handoff(payload), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return target

    def write_closed_loop_record(
        self,
        *,
        run_id: str,
        step_index: int,
        payload: dict[str, Any],
        next_tier_context: dict[str, Any] | None = None,
        opportunity_signals: list[dict[str, Any]] | None = None,
    ) -> Path:
        return self.write_record(
            run_id=run_id,
            step_index=step_index,
            payload=canonical_operator_handoff(
                payload,
                next_tier_context=next_tier_context,
                opportunity_signals=opportunity_signals,
            ),
        )

    def list_records(self) -> list[Path]:
        return sorted(self.root_dir.glob("*.json"))


__all__ = [
    "CANON_HEADLESS_OPERATOR_HANDOFF",
    "FileOperatorHandoffStore",
]
