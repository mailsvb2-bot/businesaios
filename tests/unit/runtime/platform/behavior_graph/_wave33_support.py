from __future__ import annotations

from contextlib import contextmanager

import runtime.platform.behavior_graph.postgres_behavior_graph_store as pg_module
from contracts.behavior_graph import Edge, Node
from runtime.platform.behavior_graph.postgres_behavior_graph_store import PostgresBehaviorGraphStore

NODES = [
    Node("a", "user", "a", "A", {"rank": 1}),
    Node("b", "entity", "b", "B", {}),
    Node("c", "entity", "c", "C", {"rank": 3}),
]
EDGES = [
    Edge("e1", "touched", "a", "b", 2.0, {"kind": "first"}),
    Edge("e2", "follows", "b", "c", 1.0, {}),
    Edge("e3", "touched", "a", "c", 2.0, {"kind": "tie"}),
]


class FakePort:
    instances: list[FakePort] = []
    fail_execute_at: int | None = None
    fail_rollback = False
    ping_value: object = True
    fail_exit = False

    def __init__(self, dsn: str, application_name: str = "") -> None:
        self.dsn = dsn
        self.application_name = application_name
        self.executions: list[tuple[str, object]] = []
        self.fetchall_responses: list[list[tuple]] = []
        self.fetchone_responses: list[tuple | None] = []
        self.commits = 0
        self.rollbacks = 0
        self.exits: list[tuple[object, object, object]] = []
        self.entered = False
        type(self).instances.append(self)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exits.append((exc_type, exc, tb))
        if self.fail_exit:
            raise RuntimeError("exit failed")

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if self.fail_execute_at is not None and len(self.executions) == self.fail_execute_at:
            raise RuntimeError("execute failed")

    def fetchone(self, sql, params=None):
        self.executions.append((sql, params))
        return self.fetchone_responses.pop(0) if self.fetchone_responses else None

    def fetchall(self, sql, params=None):
        self.executions.append((sql, params))
        return self.fetchall_responses.pop(0) if self.fetchall_responses else []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("rollback failed")

    def ping(self):
        if isinstance(self.ping_value, BaseException):
            raise self.ping_value
        return self.ping_value

    @contextmanager
    def transaction(self):
        try:
            yield self
        except Exception as exc:
            try:
                self.rollback()
            except Exception as rollback_exc:
                exc.add_note(f"rollback failed: {rollback_exc}")
            raise
        else:
            self.commit()


def reset_fake_port_state(monkeypatch) -> None:
    FakePort.instances = []
    FakePort.fail_execute_at = None
    FakePort.fail_rollback = False
    FakePort.ping_value = True
    FakePort.fail_exit = False
    monkeypatch.setattr(pg_module, "PostgresPort", FakePort)


def opened_store() -> tuple[PostgresBehaviorGraphStore, FakePort]:
    store = PostgresBehaviorGraphStore("postgres://test")
    port = FakePort("postgres://test")
    store._port = port
    return store, port
