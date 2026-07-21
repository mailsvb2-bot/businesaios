from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.handlers.behavior_graph as handler
from contracts.behavior_graph import Neighbor, Node, PathStep


class Store:
    def __init__(self) -> None:
        self.upserts = []
        self.nodes: dict[str, Node] = {}
        self.neighbor_rows: list[Neighbor] = []
        self.path_rows: list[PathStep] = []
        self.resets = []

    def upsert_snapshot(self, **kwargs):
        self.upserts.append(kwargs)

    def get_node(self, **kwargs):
        return self.nodes.get(kwargs["node_id"])

    def neighbors(self, **kwargs):
        self.neighbor_args = kwargs
        return self.neighbor_rows

    def shortest_path(self, **kwargs):
        self.path_args = kwargs
        return self.path_rows

    def reset(self, **kwargs):
        self.resets.append(kwargs)


class EventStore:
    def __init__(self, events):
        self.events = list(events)
        self.calls = []

    def iter_events(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.events)


class Effects:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def track_event(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("telemetry down")


def env(*, tenant_id: str = "tenant-env"):
    return SimpleNamespace(
        tenant=SimpleNamespace(tenant_id=tenant_id),
        decision=SimpleNamespace(decision_id="decision-1", correlation_id="correlation-1"),
    )


def test_scope_resolution_preserves_explicit_user_and_tenant_defaults() -> None:
    assert handler._scope_from_payload({"scope": " custom "}) == "custom"
    assert handler._scope_from_payload({"user_id": " user-1 "}) == "user:user-1"
    assert handler._scope_from_payload({}) == "tenant"


def test_build_handler_preserves_event_bounds_snapshot_and_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store()
    events = EventStore([{"event": 1}, {"event": 2}])
    effects = Effects()
    nodes = [Node("node-1", "user", "key", "Title", {"x": 1})]
    edges = []
    observed = {}

    def build_behavior_graph_from_events(**kwargs):
        observed.update(kwargs)
        return nodes, edges, {"input_events": 2}

    monkeypatch.setattr(handler, "build_behavior_graph_from_events", build_behavior_graph_from_events)
    monkeypatch.setattr(handler.time, "time", lambda: 12.345)

    result = handler.handle_behavior_graph_build(
        {
            "tenant_id": " tenant-payload ",
            "scope": " scope ",
            "user_id": " user-1 ",
            "start_ms": "10",
            "end_ms": "20",
            "max_events": "7",
            "enable_sequence_edges": False,
        },
        effects,
        env(),
        event_store=events,
        store=store,
    )
    assert events.calls == [
        {
            "tenant_id": "tenant-payload",
            "start_ms": 10,
            "end_ms": 20,
            "user_id": "user-1",
            "event_type": None,
        }
    ]
    assert observed == {"events": events.events, "max_events": 7, "enable_sequence_edges": False}
    assert store.upserts[0]["built_at_ms"] == 12_345
    assert store.upserts[0]["meta"] == {
        "input_events": 2,
        "tenant_id": "tenant-payload",
        "scope": "scope",
        "source_events": 2,
        "user_id": "user-1",
    }
    assert effects.calls[0]["source"] == "behavior_graph"
    assert result == {
        "ok": True,
        "tenant_id": "tenant-payload",
        "scope": "scope",
        "built_at_ms": 12_345,
        "meta": {"input_events": 2},
    }


def test_build_handler_defaults_env_tenant_and_swallows_telemetry_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = Store()
    events = EventStore([])
    effects = Effects(fail=True)
    monkeypatch.setattr(handler, "build_behavior_graph_from_events", lambda **_kwargs: ([], [], None))
    monkeypatch.setattr(handler.time, "time", lambda: 1.0)

    result = handler.handle_behavior_graph_build(
        None,
        effects,
        env(),
        event_store=events,
        store=store,
    )
    assert events.calls[0]["tenant_id"] == "tenant-env"
    assert events.calls[0]["start_ms"] == 0
    assert events.calls[0]["end_ms"] is None
    assert events.calls[0]["user_id"] is None
    assert store.upserts[0]["meta"]["user_id"] is None
    assert result["scope"] == "tenant"
    assert "telemetry emission failed" in caplog.text


def test_node_handler_covers_missing_not_found_and_success() -> None:
    store = Store()
    assert handler.handle_behavior_graph_node({}, None, env(), store=store) == {
        "ok": False,
        "error": "MISSING_NODE_ID",
    }
    assert handler.handle_behavior_graph_node({"node_id": " missing ", "user_id": "u"}, None, env(), store=store) == {
        "ok": False,
        "error": "NOT_FOUND",
        "node_id": "missing",
    }

    store.nodes["node-1"] = Node("node-1", "user", "key", "Title", {"x": 1})
    assert handler.handle_behavior_graph_node({"node_id": " node-1 ", "scope": "scope"}, None, env(), store=store) == {
        "ok": True,
        "node": {
            "node_id": "node-1",
            "node_type": "user",
            "key": "key",
            "title": "Title",
            "props": {"x": 1},
        },
    }


def test_neighbors_handler_preserves_query_and_projection() -> None:
    store = Store()
    assert handler.handle_behavior_graph_neighbors({}, None, env(), store=store) == {
        "ok": False,
        "error": "MISSING_NODE_ID",
    }
    store.neighbor_rows = [Neighbor("other", 2.5, "touch", "edge-1", {"x": 1})]
    result = handler.handle_behavior_graph_neighbors(
        {
            "tenant_id": "tenant",
            "scope": "scope",
            "node_id": " node ",
            "direction": " IN ",
            "limit": "4",
            "edge_type": " touch ",
        },
        None,
        env(),
        store=store,
    )
    assert store.neighbor_args == {
        "tenant_id": "tenant",
        "scope": "scope",
        "node_id": "node",
        "direction": "in",
        "limit": 4,
        "edge_type": "touch",
    }
    assert result["neighbors"] == [
        {"node_id": "other", "weight": 2.5, "edge_type": "touch", "edge_id": "edge-1", "props": {"x": 1}}
    ]


def test_path_handler_covers_missing_and_projection() -> None:
    store = Store()
    assert handler.handle_behavior_graph_path({"src": "a"}, None, env(), store=store) == {
        "ok": False,
        "error": "MISSING_SRC_DST",
    }
    store.path_rows = [PathStep("a", None, None, 0.0), PathStep("b", "e1", "touch", 1.0)]
    result = handler.handle_behavior_graph_path(
        {"tenant_id": "t", "user_id": "u", "src": " a ", "dst": " b ", "max_hops": "3"},
        None,
        env(),
        store=store,
    )
    assert store.path_args == {
        "tenant_id": "t",
        "scope": "user:u",
        "src": "a",
        "dst": "b",
        "max_hops": 3,
    }
    assert result["path"] == [
        {"node_id": "a", "via_edge_id": None, "via_edge_type": None, "weight": 0.0},
        {"node_id": "b", "via_edge_id": "e1", "via_edge_type": "touch", "weight": 1.0},
    ]


def test_reset_handler_preserves_tenant_and_scope() -> None:
    store = Store()
    result = handler.handle_behavior_graph_reset(
        {"scope": " scope "},
        None,
        env(tenant_id="tenant"),
        store=store,
    )
    assert store.resets == [{"tenant_id": "tenant", "scope": "scope"}]
    assert result == {"ok": True, "tenant_id": "tenant", "scope": "scope"}
