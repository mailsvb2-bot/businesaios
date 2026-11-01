from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from compatibility.safety_storage_exports import resolve_safety_storage_export
from .models import routine_reply_day

CANON_SAFETY_ACTION_BUDGET_LEDGER = True


class ActionBudgetLedger(Protocol):
    def snapshot(self, tenant_id: str) -> tuple[float, int]: ...

    def record(self, tenant_id: str, *, estimated_cost: float) -> None: ...


@dataclass
class InMemoryActionBudgetLedger:
    cost_by_tenant: dict[str, float] = field(default_factory=dict)
    actions_by_tenant: dict[str, int] = field(default_factory=dict)
    routine_replies_by_day: dict[tuple[str, str], int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def snapshot(self, tenant_id: str) -> tuple[float, int]:
        with self._lock:
            return float(self.cost_by_tenant.get(str(tenant_id), 0.0)), int(self.actions_by_tenant.get(str(tenant_id), 0))

    def record(self, tenant_id: str, *, estimated_cost: float) -> None:
        with self._lock:
            key = str(tenant_id)
            self.cost_by_tenant[key] = float(self.cost_by_tenant.get(key, 0.0)) + float(estimated_cost)
            self.actions_by_tenant[key] = int(self.actions_by_tenant.get(key, 0)) + 1


    def routine_reply_count(self, tenant_id: str) -> int:
        with self._lock:
            return int(self.routine_replies_by_day.get((str(tenant_id), routine_reply_day()), 0))

    def record_routine_reply(self, tenant_id: str) -> None:
        with self._lock:
            key = (str(tenant_id), routine_reply_day())
            self.routine_replies_by_day[key] = self.routine_replies_by_day.get(key, 0) + 1


def __getattr__(name: str):
    return resolve_safety_storage_export("budget_ledger", name)
__all__ = [
    'ActionBudgetLedger',
    'CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER',  # noqa: F822 - provided lazily by module __getattr__
    'CANON_SAFETY_ACTION_BUDGET_LEDGER',
    'InMemoryActionBudgetLedger',
    'SCHEMA_VERSION',  # noqa: F822 - provided lazily by module __getattr__
    'SqliteActionBudgetLedger',  # noqa: F822 - provided lazily by module __getattr__
]
