from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningJobResult:
    status: str
    snapshot_id: str | None = None
    model_id: str | None = None
    reason: str | None = None
    decision_id: str | None = None
