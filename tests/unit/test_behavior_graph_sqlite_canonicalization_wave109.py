from __future__ import annotations

from contracts.behavior_graph import Edge, Node
from runtime.platform.behavior_graph.sqlite_behavior_graph_store import SqliteBehaviorGraphStore


def test_sqlite_behavior_graph_shortest_path_and_reset(tmp_path) -> None:
    db = tmp_path / "bg.db"
    with SqliteBehaviorGraphStore(str(db)) as store:
        store.upsert_snapshot(
            tenant_id="t1",
            scope="tenant",
            built_at_ms=1,
            nodes=[
                Node(node_id="a", node_type="user", key="a", title="A", props={}),
                Node(node_id="b", node_type="user", key="b", title="B", props={}),
                Node(node_id="c", node_type="user", key="c", title="C", props={}),
            ],
            edges=[
                Edge(edge_id="e1", edge_type="next", src="a", dst="b", weight=1.0, props={}),
                Edge(edge_id="e2", edge_type="next", src="b", dst="c", weight=1.0, props={}),
            ],
            meta={},
        )
        steps = store.shortest_path(tenant_id="t1", scope="tenant", src="a", dst="c")
        assert [step.node_id for step in steps] == ["a", "b", "c"]
        store.reset(tenant_id="t1", scope="tenant")
        assert store.get_snapshot(tenant_id="t1", scope="tenant") is None
