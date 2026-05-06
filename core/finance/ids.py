from dataclasses import dataclass
from uuid import uuid4
@dataclass(frozen=True)
class FinanceSnapshotId:
    value: str
    @classmethod
    def new(cls) -> "FinanceSnapshotId":
        return cls(value=f"finance-snapshot-{uuid4().hex}")
    def __str__(self) -> str:
        return self.value
