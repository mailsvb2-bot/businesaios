from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AssumptionAuditRecord:
    key: str
    old_value: Decimal | None
    new_value: Decimal
    actor: str


class AssumptionAuditLog:
    def __init__(self) -> None:
        self._records: list[AssumptionAuditRecord] = []

    def record(self, key: str, old_value: Decimal | None, new_value: Decimal, actor: str) -> None:
        self._records.append(AssumptionAuditRecord(key=key, old_value=old_value, new_value=new_value, actor=actor))

    def records(self) -> tuple[AssumptionAuditRecord, ...]:
        return tuple(self._records)
