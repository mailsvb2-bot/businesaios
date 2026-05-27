from __future__ import annotations

import json
from dataclasses import dataclass, field

CANON_OPERATIONAL_BUDGET_LEDGER = True


@dataclass(frozen=True)
class OperationalBudgetCounters:
    actions_count: int = 0
    budget_minor: int = 0
    publications_count: int = 0
    outbound_count: int = 0
    strategic_changes_without_approval: int = 0
    rollback_triggers: int = 0


@dataclass
class InMemoryOperationalBudgetLedger:
    hourly: dict[tuple[str, str], OperationalBudgetCounters] = field(default_factory=dict)
    daily: dict[tuple[str, str], OperationalBudgetCounters] = field(default_factory=dict)
    committed_execution_ids: set[str] = field(default_factory=set)

    def get_hour(self, tenant_id: str, hour_bucket: str) -> OperationalBudgetCounters:
        return self.hourly.get((str(tenant_id), str(hour_bucket)), OperationalBudgetCounters())

    def get_day(self, tenant_id: str, day_bucket: str) -> OperationalBudgetCounters:
        return self.daily.get((str(tenant_id), str(day_bucket)), OperationalBudgetCounters())

    def commit(
        self,
        tenant_id: str,
        *,
        execution_id: str | None,
        hour_bucket: str,
        day_bucket: str,
        actions_count: int,
        budget_minor: int,
        publications_count: int,
        outbound_count: int,
        strategic_changes_without_approval: int,
        rollback_triggers: int,
    ) -> None:
        normalized_execution_id = self._execution_identity(tenant_id, execution_id)
        if normalized_execution_id is not None:
            if normalized_execution_id in self.committed_execution_ids:
                return
            self.committed_execution_ids.add(normalized_execution_id)

        hour_key = (str(tenant_id), str(hour_bucket))
        day_key = (str(tenant_id), str(day_bucket))
        self.hourly[hour_key] = self._merge(
            self.hourly.get(hour_key, OperationalBudgetCounters()),
            actions_count=actions_count,
        )
        self.daily[day_key] = self._merge(
            self.daily.get(day_key, OperationalBudgetCounters()),
            actions_count=actions_count,
            budget_minor=budget_minor,
            publications_count=publications_count,
            outbound_count=outbound_count,
            strategic_changes_without_approval=strategic_changes_without_approval,
            rollback_triggers=rollback_triggers,
        )

    @staticmethod
    def _execution_identity(tenant_id: str, execution_id: str | None) -> str | None:
        if execution_id is None:
            return None
        normalized_execution_id = str(execution_id).strip()
        if not normalized_execution_id:
            return None
        return json.dumps([str(tenant_id).strip(), normalized_execution_id], ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _merge(
        base: OperationalBudgetCounters,
        *,
        actions_count: int = 0,
        budget_minor: int = 0,
        publications_count: int = 0,
        outbound_count: int = 0,
        strategic_changes_without_approval: int = 0,
        rollback_triggers: int = 0,
    ) -> OperationalBudgetCounters:
        return OperationalBudgetCounters(
            actions_count=int(base.actions_count) + int(actions_count),
            budget_minor=int(base.budget_minor) + int(budget_minor),
            publications_count=int(base.publications_count) + int(publications_count),
            outbound_count=int(base.outbound_count) + int(outbound_count),
            strategic_changes_without_approval=(
                int(base.strategic_changes_without_approval) + int(strategic_changes_without_approval)
            ),
            rollback_triggers=int(base.rollback_triggers) + int(rollback_triggers),
        )


__all__ = [
    "InMemoryOperationalBudgetLedger",
    "OperationalBudgetCounters",
]