from __future__ import annotations

from pathlib import Path

import pytest

import runtime.platform.behavior_graph as namespace
from runtime.platform.behavior_graph.path_support import finish_shortest_path
from runtime.platform.behavior_graph.postgres_behavior_graph_store import PostgresBehaviorGraphStore
from runtime.platform.behavior_graph.sqlite_behavior_graph_store import (
    SqliteBehaviorGraphStore,
    rollback_reset,
)
from tests.unit.runtime.platform.behavior_graph._wave33_support import EDGES, NODES


def test_sqlite_end_to_end_deterministic_contract(tmp_path: Path) -> None:
    path = tmp_path / "graph.sqlite"
    with SqliteBehaviorGraphStore(str(path)) as store:
        with pytest.raises(ValueError, match="tenant_id and scope"):
            store.upsert_snapshot(tenant_id="", scope="s", built_at_ms=1, nodes=[], edges=[])
        store.upsert_snapshot(
            tenant_id="tenant",
            scope="scope",
            built_at_ms=11,
            nodes=list(reversed(NODES)),
            edges=list(reversed(EDGES)),
            meta={"source": "events"},
        )
        snapshot = store.get_snapshot(tenant_id="tenant", scope="scope")
        assert snapshot is not None
        assert [node.node_id for node in snapshot.nodes] == ["a", "b", "c"]
        assert [edge.edge_id for edge in snapshot.edges] == ["e1", "e2", "e3"]
        assert snapshot.meta["built_at_ms"] == 11
        assert store.get_snapshot(tenant_id="other", scope="scope") is None
        assert store.get_node(tenant_id="tenant", scope="scope", node_id="a") == NODES[0]
        assert store.get_node(tenant_id="tenant", scope="scope", node_id="missing") is None
        assert [n.edge_id for n in store.neighbors(tenant_id="tenant", scope="scope", node_id="a")] == ["e1", "e3"]
        assert [
            n.node_id
            for n in store.neighbors(
                tenant_id="tenant", scope="scope", node_id="c", direction="in", edge_type="touched"
            )
        ] == ["a"]
        with pytest.raises(ValueError, match="direction"):
            store.neighbors(tenant_id="tenant", scope="scope", node_id="a", direction="bad")
        assert [s.node_id for s in store.shortest_path(tenant_id="tenant", scope="scope", src="a", dst="c")] == [
            "a",
            "c",
        ]
        assert [s.node_id for s in store.shortest_path(tenant_id="tenant", scope="scope", src="a", dst="a")] == ["a"]
        assert store.shortest_path(tenant_id="tenant", scope="scope", src="c", dst="a", max_hops=1) == []
        store.reset(tenant_id="tenant", scope="scope")
        assert store.get_snapshot(tenant_id="tenant", scope="scope") is None


def test_sqlite_failure_paths_and_namespace_compatibility(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cursor:
        def __init__(self, fail_at=1):
            self.calls = 0
            self.fail_at = fail_at

        def execute(self, *_args):
            self.calls += 1
            if self.calls == self.fail_at:
                raise RuntimeError("delete failed")

    class Db:
        def __init__(self, rollback_fails=False):
            self.cur = Cursor()
            self.commits = 0
            self.rollbacks = 0
            self.rollback_fails = rollback_fails

        def cursor(self):
            return self.cur

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1
            if self.rollback_fails:
                raise RuntimeError("rollback failed")

    db = Db()
    with pytest.raises(RuntimeError, match="delete failed"):
        rollback_reset(db=db, tenant_id="t", scope="s")
    assert db.rollbacks == 1
    db2 = Db(rollback_fails=True)
    with pytest.raises(RuntimeError, match="delete failed"):
        rollback_reset(db=db2, tenant_id="t", scope="s")
    assert db2.rollbacks == 1

    assert namespace.SqliteBehaviorGraphStore is SqliteBehaviorGraphStore
    assert namespace.PostgresBehaviorGraphStore is PostgresBehaviorGraphStore
    with pytest.raises(AttributeError, match="missing"):
        namespace.__getattr__("missing")


def test_path_projection_accepts_prepopulated_identity() -> None:
    path = finish_shortest_path(
        prev={"a": ("ignored", "edge", "type", 1.0)},
        src="a",
        dst="a",
    )
    assert [step.node_id for step in path] == ["a"]


