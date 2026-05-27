from __future__ import annotations

from typing import Protocol

from core.safety.operational.operational_budget_ledger import OperationalBudgetCounters

CANON_OPERATIONAL_PORTS = True


class OperationalBudgetLedgerPort(Protocol):
    def get_hour(self, tenant_id: str, hour_bucket: str) -> OperationalBudgetCounters:
        ...

    def get_day(self, tenant_id: str, day_bucket: str) -> OperationalBudgetCounters:
        ...

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
        ...


__all__ = [
    "OperationalBudgetLedgerPort",
]