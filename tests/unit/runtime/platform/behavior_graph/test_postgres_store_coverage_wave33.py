from __future__ import annotations

import pytest

from runtime.platform.behavior_graph.path_support import finish_shortest_path
from runtime.platform.behavior_graph.postgres_behavior_graph_store import PostgresBehaviorGraphStore
from tests.unit.runtime.platform.behavior_graph._wave33_support import (
    EDGES,
    NODES,
    FakePort,
    opened_store,
    reset_fake_port_state,
)


@pytest.fixture(autouse=True)
def reset_fake_port(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_fake_port_state(monkeypatch)


def test_path_projection_is_shared_and_fail_closed() -> None:
    assert finish_shortest_path(prev={}, src="a", dst="z") == []
    path = finish_shortest_path(
        prev={
            "b": ("a", "e1", "touched", 2.0),
            "c": ("b", "e2", "follows", 1.0),
        },
        src="a",
        dst="c",
    )
    assert [step.node_id for step in path] == ["a", "b", "c"]
    assert path[1].via_edge_id == "e1"
    broken = finish_shortest_path(
        prev={"c": ("orphan", "e", "type", 1.0)},
        src="a",
        dst="c",
    )
    assert [step.node_id for step in broken] == ["orphan", "c"]


def test_postgres_context_schema_ping_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    store = PostgresBehaviorGraphStore(" postgres://db ")
    assert store._dsn == " postgres://db "
    assert store.ping() is False
    entered = store.__enter__()
    port = FakePort.instances[-1]
    assert entered is store
    assert port.application_name == "businesaios-behavior-graph"
    assert len(port.executions) == 6
    assert port.commits == 1
    assert store.ping() is True
    FakePort.ping_value = RuntimeError("down")
    assert store.ping() is False
    store.__exit__(None, None, None)
    assert store._port is None
    assert port.exits[-1][0] is None
    store.__exit__(None, None, None)

    FakePort.fail_execute_at = 1
    failed = PostgresBehaviorGraphStore("postgres://db")
    with pytest.raises(RuntimeError, match="execute failed"):
        failed.__enter__()
    failed_port = FakePort.instances[-1]
    assert failed._port is None
    assert failed_port.exits and failed_port.exits[0][0] is RuntimeError

    FakePort.fail_exit = True
    cleanup_failed = PostgresBehaviorGraphStore("postgres://db")
    with pytest.raises(RuntimeError, match="execute failed") as raised:
        cleanup_failed.__enter__()
    assert cleanup_failed._port is None
    assert any("cleanup also failed" in note for note in raised.value.__notes__)


def test_postgres_upsert_snapshot_success_validation_and_rollback() -> None:
    store, port = opened_store()
    with pytest.raises(ValueError, match="tenant_id and scope"):
        store.upsert_snapshot(tenant_id=" ", scope="s", built_at_ms=1, nodes=[], edges=[])
    with pytest.raises(ValueError, match="tenant_id and scope"):
        store.upsert_snapshot(tenant_id="t", scope=" ", built_at_ms=1, nodes=[], edges=[])

    store.upsert_snapshot(
        tenant_id=" tenant ",
        scope=" scope ",
        built_at_ms=9,
        nodes=NODES,
        edges=EDGES,
        meta={"source": "events"},
    )
    assert port.commits == 1
    assert len(port.executions) == 3 + len(NODES) + len(EDGES)
    assert port.executions[0][1][:3] == ("tenant", "scope", 9)
    assert '"built_at_ms": 9' in port.executions[0][1][3]
    assert '"rank": 1' in port.executions[3][1][-1]

    failing, failing_port = opened_store()
    failing_port.fail_execute_at = 2
    with pytest.raises(RuntimeError, match="execute failed"):
        failing.upsert_snapshot(tenant_id="t", scope="s", built_at_ms=1, nodes=NODES, edges=[])
    assert failing_port.rollbacks == 1

    masked, masked_port = opened_store()
    masked_port.fail_execute_at = 1
    masked_port.fail_rollback = True
    with pytest.raises(RuntimeError, match="execute failed"):
        masked.upsert_snapshot(tenant_id="t", scope="s", built_at_ms=1, nodes=[], edges=[])
    assert masked_port.rollbacks == 1


def test_postgres_snapshot_node_and_neighbors_preserve_contracts() -> None:
    store, port = opened_store()
    port.fetchone_responses = [None]
    assert store.get_snapshot(tenant_id=" t ", scope=" s ") is None

    port.fetchone_responses = [(7, '{"source": "events"}')]
    port.fetchall_responses = [
        [("a", "user", "a", "A", '{"rank": 1}'), ("b", "entity", "b", "B", "")],
        [("e1", "touched", "a", "b", 2, '{"x": 1}'), ("e2", "follows", "b", "c", 1, "")],
    ]
    snapshot = store.get_snapshot(tenant_id=" t ", scope=" s ")
    assert snapshot is not None
    assert snapshot.tenant_id == "t"
    assert snapshot.scope == "s"
    assert snapshot.meta == {"source": "events"}
    assert snapshot.nodes[0].props == {"rank": 1}
    assert snapshot.nodes[1].props == {}
    assert snapshot.edges[0].props == {"x": 1}
    assert snapshot.edges[1].props == {}
    assert "ORDER BY node_id" in port.executions[-2][0]
    assert "ORDER BY edge_id" in port.executions[-1][0]

    port.fetchone_responses = [None, ("a", "user", "a", "A", "")]
    assert store.get_node(tenant_id="t", scope="s", node_id="missing") is None
    assert store.get_node(tenant_id="t", scope="s", node_id=" a ").props == {}

    port.fetchall_responses = [
        [("e3", "touched", "a", "c", 2, ""), ("e1", "touched", "a", "b", 2, '{"x": 1}')],
        [("e1", "touched", "a", "b", 2, "")],
    ]
    outgoing = store.neighbors(
        tenant_id="t",
        scope="s",
        node_id="a",
        direction="OUT",
        limit=999,
        edge_type=" touched ",
    )
    assert [item.node_id for item in outgoing] == ["c", "b"]
    assert outgoing[1].props == {"x": 1}
    query, params = port.executions[-1]
    assert "src=%s" in query and "edge_type=%s" in query
    assert "weight DESC, edge_id ASC" in query
    assert params[-1] == 500

    incoming = store.neighbors(tenant_id="t", scope="s", node_id="b", direction="in", limit=0)
    assert incoming[0].node_id == "a"
    query, params = port.executions[-1]
    assert "dst=%s" in query and "edge_type=%s" not in query
    assert params[-1] == 1

    with pytest.raises(ValueError, match="direction"):
        store.neighbors(tenant_id="t", scope="s", node_id="a", direction="sideways")


def test_postgres_shortest_path_and_reset_transactions() -> None:
    store, port = opened_store()
    same = store.shortest_path(tenant_id="t", scope="s", src="a", dst="a")
    assert [step.node_id for step in same] == ["a"]

    port.fetchall_responses = [
        [("e1", "touched", "a", "b", 1), ("cycle", "touched", "a", "a", 1)],
        [("back", "follows", "b", "a", 1), ("e2", "follows", "b", "c", 1)],
    ]
    path = store.shortest_path(tenant_id="t", scope="s", src="a", dst="c", max_hops=99)
    assert [step.node_id for step in path] == ["a", "b", "c"]
    assert all("ORDER BY edge_id ASC" in sql for sql, _ in port.executions[-2:])

    port.fetchall_responses = [[("e1", "touched", "a", "b", 1)]]
    assert store.shortest_path(tenant_id="t", scope="s", src="a", dst="z", max_hops=1) == []

    store.reset(tenant_id=" tenant ", scope=" scope ")
    assert port.commits == 1
    assert [params for _, params in port.executions[-3:]] == [
        ("tenant", "scope"),
        ("tenant", "scope"),
        ("tenant", "scope"),
    ]

    failing, failing_port = opened_store()
    failing_port.fail_execute_at = 2
    with pytest.raises(RuntimeError, match="execute failed"):
        failing.reset(tenant_id="t", scope="s")
    assert failing_port.rollbacks == 1

    masked, masked_port = opened_store()
    masked_port.fail_execute_at = 1
    masked_port.fail_rollback = True
    with pytest.raises(RuntimeError, match="execute failed"):
        masked.reset(tenant_id="t", scope="s")
    assert masked_port.rollbacks == 1


