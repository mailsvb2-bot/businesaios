from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EconomicsSnapshotBuilt:
    snapshot_id: str
    built_at: datetime
    blocking_guard: bool
