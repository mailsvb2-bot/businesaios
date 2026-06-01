from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoiSnapshot:
    snapshot_id: str = ''
    roi: float = 0.0
    period_days: str = ''
