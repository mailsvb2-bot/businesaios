from __future__ import annotations

from pathlib import Path

from core.safety.operational.persistent_operational_budget_ledger import (
    PersistentOperationalBudgetLedger,
)


def test_persistent_ledger_survives_restart(tmp_path: Path) -> None:
    storage_path = tmp_path / "operational_ledger.json"

    first = PersistentOperationalBudgetLedger(storage_path=storage_path)
    first.commit(
        "tenant-a",
        execution_id="exec-1",
        hour_bucket="2026-03-21T10",
        day_bucket="2026-03-21",
        actions_count=1,
        budget_minor=120,
        publications_count=2,
        outbound_count=3,
        strategic_changes_without_approval=0,
        rollback_triggers=1,
    )

    second = PersistentOperationalBudgetLedger(storage_path=storage_path)
    hour = second.get_hour("tenant-a", "2026-03-21T10")
    day = second.get_day("tenant-a", "2026-03-21")

    assert hour.actions_count == 1
    assert day.actions_count == 1
    assert day.budget_minor == 120
    assert day.publications_count == 2
    assert day.outbound_count == 3
    assert day.rollback_triggers == 1


def test_persistent_ledger_commit_is_idempotent_by_execution_id_per_tenant(tmp_path: Path) -> None:
    storage_path = tmp_path / "operational_ledger.json"
    ledger = PersistentOperationalBudgetLedger(storage_path=storage_path)

    ledger.commit(
        "tenant-a",
        execution_id="dup-1",
        hour_bucket="2026-03-21T10",
        day_bucket="2026-03-21",
        actions_count=1,
        budget_minor=50,
        publications_count=0,
        outbound_count=0,
        strategic_changes_without_approval=0,
        rollback_triggers=0,
    )
    ledger.commit(
        "tenant-a",
        execution_id="dup-1",
        hour_bucket="2026-03-21T10",
        day_bucket="2026-03-21",
        actions_count=1,
        budget_minor=50,
        publications_count=0,
        outbound_count=0,
        strategic_changes_without_approval=0,
        rollback_triggers=0,
    )
    ledger.commit(
        "tenant-b",
        execution_id="dup-1",
        hour_bucket="2026-03-21T10",
        day_bucket="2026-03-21",
        actions_count=1,
        budget_minor=70,
        publications_count=0,
        outbound_count=0,
        strategic_changes_without_approval=0,
        rollback_triggers=0,
    )

    day_a = ledger.get_day("tenant-a", "2026-03-21")
    day_b = ledger.get_day("tenant-b", "2026-03-21")
    assert day_a.actions_count == 1
    assert day_a.budget_minor == 50
    assert day_b.actions_count == 1
    assert day_b.budget_minor == 70