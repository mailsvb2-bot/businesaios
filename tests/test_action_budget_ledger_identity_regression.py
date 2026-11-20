import pytest

from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger


@pytest.mark.parametrize("tenant,key", [
    ("", "event-1"),
    ("  ", "event-1"),
    ("tenant-1", ""),
    ("tenant-1", "  "),
])
def test_atomic_budget_rejects_missing_identity_without_writing(tmp_path, tenant, key):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / "budget.sqlite"))
    with pytest.raises(ValueError, match="tenant_id and idempotency_key"):
        ledger.record_once(
            tenant, idempotency_key=key, action="reply",
            payload_hash="fingerprint", estimated_cost=2.0,
        )
    with pytest.raises(ValueError, match="tenant_id and idempotency_key"):
        ledger.recorded_action(tenant, key)
    assert ledger.snapshot("tenant-1") == (0.0, 0)
    assert ledger.snapshot("unknown") == (0.0, 0)


def test_atomic_budget_retry_is_tenant_scoped_and_conflicts_fail_closed(tmp_path):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / "budget.sqlite"))
    kwargs = dict(idempotency_key="update-1", action="reply", payload_hash="a", estimated_cost=2.0)
    assert ledger.record_once("tenant-a", **kwargs) is True
    assert ledger.record_once("tenant-a", **kwargs) is False
    assert ledger.record_once("tenant-b", **kwargs) is True
    with pytest.raises(RuntimeError, match="action_budget_idempotency_conflict"):
        ledger.record_once("tenant-a", **(kwargs | {"payload_hash": "b"}))
    assert ledger.snapshot("tenant-a") == (2.0, 1)
    assert ledger.snapshot("tenant-b") == (2.0, 1)


def test_budget_overflow_rolls_back_idempotency_and_total(tmp_path):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / "budget.sqlite"))
    assert ledger.record_once("tenant-a", idempotency_key="first", action="reply",
                              payload_hash="a", estimated_cost=1e308)
    with pytest.raises(RuntimeError, match="action_budget_corrupt_total"):
        ledger.record_once("tenant-a", idempotency_key="second", action="reply",
                           payload_hash="b", estimated_cost=1e308)
    assert ledger.recorded_action("tenant-a", "second") is None
    assert ledger.snapshot("tenant-a") == (1e308, 1)


@pytest.mark.parametrize("cost,actions", [
    (float("inf"), 1), (-1.0, 1),
    ("invalid", 1), (1.0, -1), (1.0, "invalid"),
])
def test_budget_corrupt_persisted_totals_fail_closed(tmp_path, cost, actions):
    import sqlite3

    path = tmp_path / "budget.sqlite"
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(path))
    assert ledger.record_once("tenant-a", idempotency_key="first", action="reply",
                              payload_hash="a", estimated_cost=1.0)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE safety_action_budget_ledger SET total_cost=?, total_actions=? WHERE tenant_id=?",
            (cost, actions, "tenant-a"),
        )
    with pytest.raises(RuntimeError, match="action_budget_corrupt_total"):
        ledger.snapshot("tenant-a")
    with pytest.raises(RuntimeError, match="action_budget_corrupt_total"):
        ledger.record_once("tenant-a", idempotency_key="first", action="reply",
                           payload_hash="a", estimated_cost=1.0)
    with pytest.raises(RuntimeError, match="action_budget_corrupt_total"):
        ledger.record_once("tenant-a", idempotency_key="second", action="reply",
                           payload_hash="b", estimated_cost=1.0)
    assert ledger.recorded_action("tenant-a", "second") is None
