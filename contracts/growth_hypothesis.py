from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GrowthHypothesis:
    hypothesis_id: str = ''
    summary: str = ''
    channel: str = ''
