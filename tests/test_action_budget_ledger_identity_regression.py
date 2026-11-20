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
