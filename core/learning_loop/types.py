"""Learning-loop types. Canonical decision flow remains DecisionCore -> RuntimeExecutor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningBatch:
    """Input for policy-update proposal building (learning loop)."""
    batch_id: str
    sample_count: int = 0

    def __post_init__(self) -> None:
        if not str(self.batch_id or "").strip():
            raise ValueError("batch_id is required")


__all__ = ["LearningBatch"]
