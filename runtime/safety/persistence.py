"""Runtime-owned construction of persistent safety-control stores."""

from __future__ import annotations

from runtime.safety import PersistentSafetyStores, safety_sqlite_path
from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger
from runtime.platform.safety_approval_repository import PlatformSqliteApprovalRepository
from runtime.platform.safety_circuit_breaker_store import PlatformSqliteCircuitBreakerStore
from runtime.platform.safety_rollback_store import PlatformSqliteRollbackPlanStore
from runtime.platform.safety_runaway_loop_store import PlatformSqliteRunawayLoopStore
from runtime.service_names import RuntimeServiceName

CANON_RUNTIME_SAFETY_PERSISTENCE_OWNER = True


def build_persistent_safety_stores(*, repetition_threshold: int) -> PersistentSafetyStores:
    return PersistentSafetyStores(
        circuit_breaker_store=PlatformSqliteCircuitBreakerStore(
            sqlite_path=safety_sqlite_path("circuit_breaker")
        ),
        action_budget_ledger=PlatformSqliteActionBudgetLedger(
            sqlite_path=safety_sqlite_path(RuntimeServiceName.ACTION_BUDGET)
        ),
        approval_repository=PlatformSqliteApprovalRepository(
            sqlite_path=safety_sqlite_path("approval")
        ),
        runaway_loop_store=PlatformSqliteRunawayLoopStore(
            sqlite_path=safety_sqlite_path("runaway_loop"),
            maxlen=max(int(repetition_threshold) + 2, 5),
        ),
        rollback_plan_store=PlatformSqliteRollbackPlanStore(
            sqlite_path=safety_sqlite_path("rollback_plans")
        ),
    )


__all__ = [
    "CANON_RUNTIME_SAFETY_PERSISTENCE_OWNER",
    "build_persistent_safety_stores",
]
