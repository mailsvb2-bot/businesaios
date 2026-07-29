from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from compatibility.safety_storage_exports import resolve_safety_storage_export

CANON_SAFETY_ACTION_BUDGET_LEDGER = True


class ActionBudgetLedger(Protocol):
    def snapshot(self, tenant_id: str) -> tuple[float, int]: ...

    def record(self, tenant_id: str, *, estimated_cost: float) -> None: ...


@dataclass
class InMemoryActionBudgetLedger:
    cost_by_tenant: dict[str, float] = field(default_factory=dict)
    actions_by_tenant: dict[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def snapshot(self, tenant_id: str) -> tuple[float, int]:
        with self._lock:
            return float(self.cost_by_tenant.get(str(tenant_id), 0.0)), int(self.actions_by_tenant.get(str(tenant_id), 0))

    def record(self, tenant_id: str, *, estimated_cost: float) -> None:
        with self._lock:
            key = str(tenant_id)
            self.cost_by_tenant[key] = float(self.cost_by_tenant.get(key, 0.0)) + float(estimated_cost)
            self.actions_by_tenant[key] = int(self.actions_by_tenant.get(key, 0)) + 1


def __getattr__(name: str):
    return resolve_safety_storage_export("budget_ledger", name)
__all__ = [
    'ActionBudgetLedger',
    'CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER',
    'CANON_SAFETY_ACTION_BUDGET_LEDGER',
    'InMemoryActionBudgetLedger',
    'SCHEMA_VERSION',
    'SqliteActionBudgetLedger',
]
