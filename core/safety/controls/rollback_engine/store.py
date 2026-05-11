from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from runtime.platform.safety_rollback_store import (
    CANON_PLATFORM_SAFETY_ROLLBACK_STORE,
    PlatformSqliteRollbackPlanStore,
    SCHEMA_VERSION,
)

from .models import RollbackExecutionState, RollbackPlan, RollbackReceipt, RollbackReconciliationState

CANON_SAFETY_ROLLBACK_STORE = True


class RollbackPlanStore(Protocol):
    def put(self, *, tenant_id: str, action_id: str, plan: RollbackPlan) -> RollbackPlan: ...
    def get(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None: ...
    def update_state(self, *, tenant_id: str, action_id: str, state: RollbackExecutionState) -> RollbackPlan | None: ...
    def append_receipt(self, *, tenant_id: str, action_id: str, receipt: RollbackReceipt) -> RollbackPlan | None: ...
    def update_reconciliation(self, *, tenant_id: str, action_id: str, state: RollbackReconciliationState, error: str = '') -> RollbackPlan | None: ...


class InMemoryRollbackPlanStore:
    def __init__(self) -> None:
        self._plans: dict[str, RollbackPlan] = {}
        self._lock = RLock()

    def put(self, *, tenant_id: str, action_id: str, plan: RollbackPlan) -> RollbackPlan:
        with self._lock:
            key = _key(tenant_id=tenant_id, action_id=action_id)
            current = self._plans.get(key)
            version = int(plan.version if plan.version else ((current.version + 1) if current else 1))
            stored = RollbackPlan(**{**plan.__dict__, 'version': version})
            self._plans[key] = stored
            return stored

    def get(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        with self._lock:
            return self._plans.get(_key(tenant_id=tenant_id, action_id=action_id))

    def acquire_lease(self, *, tenant_id: str, action_id: str, owner: str) -> RollbackPlan | None:
        with self._lock:
            plan = self.get(tenant_id=tenant_id, action_id=action_id)
            if plan is None:
                return None
            leased = RollbackPlan(**{**plan.__dict__, 'lease_owner': str(owner), 'version': int(plan.version) + 1, 'fencing_token': int(plan.fencing_token) + 1})
            self._plans[_key(tenant_id=tenant_id, action_id=action_id)] = leased
            return leased

    def compare_and_set(self, *, tenant_id: str, action_id: str, expected_version: int, plan: RollbackPlan) -> RollbackPlan:
        with self._lock:
            current = self.get(tenant_id=tenant_id, action_id=action_id)
            current_version = int(current.version if current else 0)
            if current_version != int(expected_version):
                raise RuntimeError('rollback_plan_version_conflict')
            if current and current.lease_owner and plan.lease_owner and current.lease_owner != plan.lease_owner and int(plan.fencing_token or 0) < int(current.fencing_token or 0):
                raise RuntimeError('rollback_plan_stale_fencing_token')
            stored = RollbackPlan(**{**plan.__dict__, 'version': int(expected_version) + 1, 'fencing_token': max(int(plan.fencing_token or 0), int((current.fencing_token if current else 0) or 0))})
            self._plans[_key(tenant_id=tenant_id, action_id=action_id)] = stored
            return stored

    def update_state(self, *, tenant_id: str, action_id: str, state: RollbackExecutionState) -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(tenant_id=tenant_id, action_id=action_id, expected_version=int(plan.version), plan=RollbackPlan(**{**plan.__dict__, 'execution_state': state}))

    def append_receipt(self, *, tenant_id: str, action_id: str, receipt: RollbackReceipt) -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(tenant_id=tenant_id, action_id=action_id, expected_version=int(plan.version), plan=RollbackPlan(**{**plan.__dict__, 'receipts': tuple([*plan.receipts, receipt])}))

    def update_reconciliation(self, *, tenant_id: str, action_id: str, state: RollbackReconciliationState, error: str = '') -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(tenant_id=tenant_id, action_id=action_id, expected_version=int(plan.version), plan=RollbackPlan(**{**plan.__dict__, 'reconciliation_state': state, 'reconciliation_error': str(error or '')}))


class SqliteRollbackPlanStore(PlatformSqliteRollbackPlanStore):
    """Safety-facing rollback plan store facade.

    SQLite ownership lives in runtime.platform.safety_rollback_store.
    """


def _key(*, tenant_id: str, action_id: str) -> str:
    return f"{str(tenant_id).strip() or 'unknown'}::{str(action_id).strip()}"


__all__ = [
    'CANON_PLATFORM_SAFETY_ROLLBACK_STORE',
    'CANON_SAFETY_ROLLBACK_STORE',
    'RollbackPlanStore',
    'InMemoryRollbackPlanStore',
    'SCHEMA_VERSION',
    'SqliteRollbackPlanStore',
]
