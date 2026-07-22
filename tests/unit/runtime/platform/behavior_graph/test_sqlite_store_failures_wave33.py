from __future__ import annotations

from pathlib import Path

import pytest

from runtime.platform.behavior_graph.sqlite_behavior_graph_store import SqliteBehaviorGraphStore
from tests.unit.runtime.platform.behavior_graph._wave33_support import EDGES, NODES


def test_sqlite_exit_and_upsert_failures_preserve_original_error() -> None:
    class FailingCloseDb:
        def commit(self):
            raise RuntimeError("commit failed")

        def close(self):
            raise RuntimeError("close failed")

    store = SqliteBehaviorGraphStore(":memory:")
    store.__exit__(None, None, None)
    store._db = FailingCloseDb()
    store.__exit__(None, None, None)
    assert store._db is None

    class Cursor:
        def __init__(self):
            self.calls = 0

        def execute(self, *_args):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("write failed")

        def executemany(self, *_args):
            raise AssertionError("not reached")

    class FailingWriteDb:
        def __init__(self, rollback_fails: bool):
            self.cur = Cursor()
            self.rollbacks = 0
            self.rollback_fails = rollback_fails

        def cursor(self):
            return self.cur

        def rollback(self):
            self.rollbacks += 1
            if self.rollback_fails:
                raise RuntimeError("rollback failed")

    for rollback_fails in (False, True):
        store = SqliteBehaviorGraphStore(":memory:")
        db = FailingWriteDb(rollback_fails)
        store._db = db
        with pytest.raises(RuntimeError, match="write failed"):
            store.upsert_snapshot(
                tenant_id="t",
                scope="s",
                built_at_ms=1,
                nodes=[],
                edges=[],
            )
        assert db.rollbacks == 1


def test_sqlite_shortest_path_depth_and_seen_branches(tmp_path: Path) -> None:
    path = tmp_path / "branches.sqlite"
    with SqliteBehaviorGraphStore(str(path)) as store:
        store.upsert_snapshot(
            tenant_id="tenant",
            scope="scope",
            built_at_ms=1,
            nodes=NODES,
            edges=EDGES,
        )
        assert (
            store.shortest_path(
                tenant_id="tenant",
                scope="scope",
                src="a",
                dst="missing",
                max_hops=6,
            )
            == []
        )
        store.upsert_snapshot(
            tenant_id="tenant",
            scope="deep",
            built_at_ms=1,
            nodes=NODES,
            edges=EDGES[:2],
        )
        assert (
            store.shortest_path(
                tenant_id="tenant",
                scope="deep",
                src="a",
                dst="c",
                max_hops=1,
            )
            == []
        )
