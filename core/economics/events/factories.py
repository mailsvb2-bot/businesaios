from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..guard import GuardTrigger
from ..ids import BudgetGuardEventId
from ..types import EconomicsSnapshot
from .budget_guard_triggered import BudgetGuardTriggered
from .economics_snapshot_built import EconomicsSnapshotBuilt


@dataclass
class EconomicsEventFactory:
    def build_snapshot_built(self, snapshot: EconomicsSnapshot) -> EconomicsSnapshotBuilt:
        return EconomicsSnapshotBuilt(
            snapshot_id=snapshot.snapshot_id.value,
            built_at=snapshot.built_at,
            blocking_guard=snapshot.has_blocking_guard,
        )

    def build_guard_triggered(self, snapshot: EconomicsSnapshot, trigger: GuardTrigger, occurred_at: datetime | None = None) -> BudgetGuardTriggered:
        return BudgetGuardTriggered(
            event_id=BudgetGuardEventId.new().value,
            snapshot_id=snapshot.snapshot_id.value,
            guard_code=trigger.code,
            severity=trigger.severity.value,
            message=trigger.message,
            occurred_at=occurred_at or snapshot.built_at,
            details=dict(trigger.details),
        )
