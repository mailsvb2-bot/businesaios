from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class EconomicsSnapshotId:
    value: str

    @classmethod
    def new(cls) -> EconomicsSnapshotId:
        return cls(value=f"eco_snap_{uuid4().hex}")


@dataclass(frozen=True)
class BudgetGuardEventId:
    value: str

    @classmethod
    def new(cls) -> BudgetGuardEventId:
        return cls(value=f"eco_guard_{uuid4().hex}")
