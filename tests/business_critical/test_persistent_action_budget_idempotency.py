from concurrent.futures import ThreadPoolExecutor

import pytest

from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger


def test_sqlite_action_budget_retry_is_atomic_and_preserves_existing_totals(tmp_path):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / "safety.sqlite3"))
    ledger.record("tenant-live", estimated_cost=2.5)
    key = "telegram:0123456789abcdef"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            lambda _index: ledger.record_once(
                "tenant-live", idempotency_key=key,
                action="bookings@v1", payload_hash="payload-v1", estimated_cost=3.5,
            ),
            range(4),
        ))

    assert sum(results) == 1
    assert ledger.recorded_action("tenant-live", key) == "bookings@v1"
    assert ledger.snapshot("tenant-live") == (6.0, 2)
    with pytest.raises(RuntimeError, match="action_budget_idempotency_conflict"):
        ledger.record_once(
            "tenant-live", idempotency_key=key,
            action="capture_payment@v1", payload_hash="payload-v2", estimated_cost=99.0,
        )
    assert ledger.snapshot("tenant-live") == (6.0, 2)
