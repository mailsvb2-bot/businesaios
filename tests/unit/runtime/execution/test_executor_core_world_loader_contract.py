from __future__ import annotations

from runtime.execution.executor_core import load_world


def test_load_world_uses_canonical_world_loader() -> None:
    assert load_world(None, "snapshot-1") == {
        "mode": "degraded",
        "reason": "no_snapshot_store",
    }
