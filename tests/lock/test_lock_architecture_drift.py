from __future__ import annotations

from pathlib import Path

from scripts.arch_drift_detector import main

ROOT = Path(__file__).resolve().parents[2]


def test_architecture_drift_detector_passes():
    assert main() == 0


def test_safety_persistence_is_runtime_owned_with_identity_compatibility() -> None:
    from core.safety.controls.action_budget.ledger import SqliteActionBudgetLedger
    from core.safety.controls.circuit_breaker.store import SqliteCircuitBreakerStore
    from core.safety.controls.multi_step_approval.repository import SqliteApprovalRepository
    from core.safety.controls.rollback_engine.store import SqliteRollbackPlanStore
    from core.safety.controls.runaway_loop_guard.store import SqliteRunawayLoopStore
    from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger
    from runtime.platform.safety_approval_repository import PlatformSqliteApprovalRepository
    from runtime.platform.safety_circuit_breaker_store import PlatformSqliteCircuitBreakerStore
    from runtime.platform.safety_rollback_store import PlatformSqliteRollbackPlanStore
    from runtime.platform.safety_runaway_loop_store import PlatformSqliteRunawayLoopStore

    assert SqliteActionBudgetLedger is PlatformSqliteActionBudgetLedger
    assert SqliteCircuitBreakerStore is PlatformSqliteCircuitBreakerStore
    assert SqliteApprovalRepository is PlatformSqliteApprovalRepository
    assert SqliteRollbackPlanStore is PlatformSqliteRollbackPlanStore
    assert SqliteRunawayLoopStore is PlatformSqliteRunawayLoopStore

    profile_source = (ROOT / "core/safety/controls/profile.py").read_text(encoding="utf-8")
    assert "runtime.platform" not in profile_source
    assert "persistent_store_factory" in profile_source
    assert "persistent safety stores require runtime composition wiring" in profile_source
