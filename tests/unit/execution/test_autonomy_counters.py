from __future__ import annotations

from pathlib import Path

from execution.autonomy_counters import FileAutonomyCounterStore


def test_counter_store_persists_counts(tmp_path: Path) -> None:
    store = FileAutonomyCounterStore(root_dir=tmp_path)
    store.record_step(tenant_id="t1", business_id="b1", recent_action={"outbound_count": 2, "irreversible_count": 1, "budget_change_amount": 5.0, "publication_count": 3})
    counters = store.load(tenant_id="t1", business_id="b1")
    assert counters.actions_day == 1
    assert counters.outbound_total == 2
    assert counters.irreversible_total == 1
    assert counters.budget_change_total == 5.0
    assert counters.publication_total == 3
