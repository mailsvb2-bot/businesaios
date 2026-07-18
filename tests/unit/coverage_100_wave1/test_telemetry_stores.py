from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from observability.platform.telemetry.event_store import (
    JsonlEventStore,
    SqliteEventStore,
    _normalized_event_types,
    _ts_iso_to_ms,
    build_default_event_store,
)
from observability.platform.telemetry.event_stream import InMemoryEventStore


def test_event_type_and_timestamp_helpers_cover_normalization_edges() -> None:
    assert _normalized_event_types(event_type=" ignored ", event_types=[" a ", "", "b"]) == {"a", "b"}
    assert _normalized_event_types(event_type=" alpha ", event_types=None) == {"alpha"}
    assert _normalized_event_types(event_type=" ", event_types=[]) is None
    assert _ts_iso_to_ms("broken") == 0
    assert _ts_iso_to_ms("1970-01-01T00:00:01") == 1000
    assert _ts_iso_to_ms("1970-01-01T00:00:02Z") == 2000


def test_jsonl_store_validation_filters_corrupt_rows_and_zero_limit(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    store = JsonlEventStore(path)
    assert store.path == path
    with pytest.raises(ValueError, match="tenant_id"):
        store.append(tenant_id=" ", user_id=None, event_type="ok", payload={})
    with pytest.raises(ValueError, match="event_type"):
        store.append(tenant_id="tenant-a", user_id=None, event_type=" ", payload={})

    store.append(tenant_id="tenant-a", user_id="u1", event_type="alpha", payload={"set": {2, 1}})
    store.append(tenant_id="tenant-b", user_id="u1", event_type="alpha", payload={"skip": True})
    store.append(tenant_id="tenant-a", user_id="u2", event_type="beta", payload={"value": 2})
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
        handle.write("[]\n")
        handle.write("\n")

    assert store.latest_events(tenant_id="tenant-a", limit=0) == []
    latest = list(store.latest_events(tenant_id="tenant-a", event_types=[" beta ", ""], limit=2))
    assert [row["event_type"] for row in latest] == ["beta"]
    assert store.latest_event(tenant_id="tenant-a", user_id="u1", event_type="alpha")["payload"]
    assert store.latest_event(tenant_id="missing") is None

    rows = list(store._read_all())
    alpha_ms = _ts_iso_to_ms(rows[0]["ts_iso"])
    assert list(store.iter_events(tenant_id="tenant-a", limit=0)) == []
    assert list(store.iter_events(tenant_id="tenant-a", user_id="u1", start_ms=alpha_ms, end_ms=alpha_ms, limit=1))[0]["event_type"] == "alpha"
    beta_ms = _ts_iso_to_ms(rows[2]["ts_iso"])
    assert list(store.iter_events(tenant_id="tenant-a", event_type="beta", end_ms=beta_ms - 1)) == []
    assert list(store.iter_events(tenant_id="tenant-a", event_types=["missing"])) == []

    store.close()
    store.close()
    path.unlink()
    assert list(store._iter_lines()) == []
    with JsonlEventStore(path) as entered:
        assert entered is not None


def test_sqlite_store_all_filters_payload_recovery_and_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.sqlite3"
    store = SqliteEventStore(path)
    assert store.path == path
    with pytest.raises(ValueError, match="tenant_id"):
        store.append(tenant_id="", user_id=None, event_type="alpha", payload={})
    with pytest.raises(ValueError, match="event_type"):
        store.append(tenant_id="tenant-a", user_id=None, event_type="", payload={})

    store.append(tenant_id="tenant-a", user_id="u1", event_type="alpha", payload={"value": 1})
    store.append(tenant_id="tenant-a", user_id="u2", event_type="beta", payload={"value": 2})
    store.append(tenant_id="tenant-b", user_id="u1", event_type="alpha", payload={"value": 3})
    ts_values = [row[0] for row in store._conn.execute("SELECT ts_ms FROM telemetry_events ORDER BY rowid").fetchall()]
    store._conn.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("bad-json", "tenant-a", None, "corrupt", "{", "1970-01-01T00:00:01+00:00", 1000),
    )
    store._conn.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("list-json", "tenant-a", None, "list", "[]", "1970-01-01T00:00:02+00:00", 2000),
    )
    store._conn.commit()

    assert list(store.latest_events(tenant_id="tenant-a", limit=0)) == []
    assert [row["event_type"] for row in store.latest_events(tenant_id="tenant-a", user_id="u1", event_types=["alpha", "beta"])] == ["alpha"]
    assert store.latest_event(tenant_id="tenant-a", event_type="missing") is None
    recovered = list(store.iter_events(tenant_id="tenant-a", event_types=["corrupt", "list"], start_ms=0, end_ms=3000, limit=2))
    assert [row["payload"] for row in recovered] == [{}, {}]
    assert list(store.iter_events(tenant_id="tenant-a", start_ms=max(ts_values) + 1)) == []
    assert list(store.iter_events(tenant_id="tenant-a", end_ms=0)) == []
    assert list(store.iter_events(tenant_id="tenant-a", limit=0)) == []

    store.close()
    store.close()
    with SqliteEventStore(path) as entered:
        assert entered.path == path


def test_build_default_event_store_selects_all_backends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    memory = build_default_event_store(backend="memory", path=tmp_path / "memory")
    assert isinstance(memory, InMemoryEventStore)
    jsonl = build_default_event_store(backend="file", path=tmp_path / "events.jsonl")
    assert isinstance(jsonl, JsonlEventStore)
    sqlite = build_default_event_store(backend="unknown", path=tmp_path / "events.sqlite3")
    assert isinstance(sqlite, SqliteEventStore)
    sqlite.close()

    monkeypatch.setenv("BUSINESAIOS_TELEMETRY_EVENT_STORE_BACKEND", "jsonl")
    from_env = build_default_event_store(path=tmp_path / "env.jsonl")
    assert isinstance(from_env, JsonlEventStore)
    config = SimpleNamespace(
        telemetry_event_store_backend="memory",
        telemetry_event_store_path=tmp_path / "configured.sqlite3",
    )
    assert isinstance(build_default_event_store(config_surface=config), InMemoryEventStore)


def test_in_memory_iter_limit_zero_is_consistent() -> None:
    store = InMemoryEventStore()
    store.append(tenant_id="tenant-a", user_id=None, event_type="alpha", payload={})
    assert list(store.iter_events(tenant_id="tenant-a", limit=0)) == []


def test_event_store_remaining_backend_branches(tmp_path: Path) -> None:
    existing_path = tmp_path / "existing.jsonl"
    existing_path.write_text("\n", encoding="utf-8")
    store = JsonlEventStore(existing_path)
    closed: list[bool] = []
    store._conn = SimpleNamespace(close=lambda: closed.append(True))
    store.close()
    assert closed == [True]

    rows = [
        {"tenant_id": "tenant-a", "user_id": None, "event_type": "alpha", "ts_iso": "1970-01-01T00:00:01+00:00"},
        {"tenant_id": "tenant-a", "user_id": None, "event_type": "beta", "ts_iso": "1970-01-01T00:00:03+00:00"},
        {"tenant_id": "tenant-a", "user_id": None, "event_type": "alpha", "ts_iso": "1970-01-01T00:00:04+00:00"},
    ]
    store = JsonlEventStore(existing_path)
    store._read_all = lambda: rows
    assert [row["ts_iso"] for row in store.iter_events(tenant_id="tenant-a", event_type="alpha", end_ms=3500, limit=1)] == ["1970-01-01T00:00:01+00:00"]
    assert list(store.iter_events(tenant_id="tenant-a", event_type="missing")) == []

    sqlite = SqliteEventStore(tmp_path / "remaining.sqlite3")
    sqlite.append(tenant_id="tenant-a", user_id=None, event_type="alpha", payload={})
    assert len(list(sqlite.iter_events(tenant_id="tenant-a", event_types=["alpha"]))) == 1
    sqlite.close()


def test_in_memory_store_full_read_contract_and_sink() -> None:
    from observability.platform.telemetry.event_stream import EventStoreSink, TelemetryEvent

    event = TelemetryEvent("id", "tenant-a", None, "alpha", {"value": 1}, "1970-01-01T00:00:01+00:00")
    assert event.as_dict()["payload"] == {"value": 1}
    store = InMemoryEventStore()
    sink = EventStoreSink(store=store)
    sink.emit(tenant_id="tenant-a", user_id="u1", event_type="alpha", payload={"value": 1})
    sink.emit(tenant_id="tenant-a", user_id="u2", event_type="beta", payload={"value": 2})
    sink.emit(tenant_id="tenant-b", user_id="u1", event_type="alpha", payload={})
    assert store.latest_events(tenant_id="tenant-a", limit=0) == []
    assert [row["event_type"] for row in store.latest_events(tenant_id="tenant-a", user_id="u1", event_types=["alpha"])] == ["alpha"]
    assert store.latest_event(tenant_id="tenant-a", event_type="beta")["user_id"] == "u2"
    assert store.latest_event(tenant_id="missing") is None
    ts = store._ts_iso_to_ms(store._events[0]["ts_iso"])
    assert [row["event_type"] for row in store.iter_events(tenant_id="tenant-a", user_id="u1", event_type="alpha", start_ms=ts, end_ms=ts, limit=1)] == ["alpha"]
    assert list(store.iter_events(tenant_id="tenant-a", event_type="missing")) == []
    assert list(store.iter_events(tenant_id="tenant-a", start_ms=ts + 10**9)) == []
    assert list(store.iter_events(tenant_id="tenant-a", end_ms=0)) == []
    assert store._normalized_event_types(event_type="alpha", event_types=None) == {"alpha"}
    assert store._normalized_event_types(event_type=None, event_types=["a", "b"]) == {"a", "b"}
    assert store._normalized_event_types(event_type=None, event_types=None) is None
    assert store._ts_iso_to_ms("broken") == 0


def test_event_store_closes_remaining_filter_and_limit_branches(tmp_path: Path) -> None:
    rows = [
        {"tenant_id": "tenant-a", "user_id": "u2", "event_type": "alpha", "ts_iso": "1970-01-01T00:00:01+00:00"},
        {"tenant_id": "tenant-a", "user_id": "u1", "event_type": "alpha", "ts_iso": "1970-01-01T00:00:02+00:00"},
    ]
    store = JsonlEventStore(tmp_path / "filters.jsonl")
    store._read_all = lambda: rows
    assert [row["user_id"] for row in store.iter_events(tenant_id="tenant-a", user_id="u1", limit=5)] == ["u1"]
    assert [row["user_id"] for row in store.iter_events(tenant_id="tenant-a", start_ms=1500, limit=5)] == ["u1"]

    sqlite = SqliteEventStore(tmp_path / "filters.sqlite3")
    sqlite.append(tenant_id="tenant-a", user_id="u1", event_type="alpha", payload={})
    assert len(list(sqlite.iter_events(tenant_id="tenant-a", user_id="u1", event_types=["alpha"]))) == 1
    sqlite.close()


def test_in_memory_remaining_filter_and_non_exhausted_limit_branches() -> None:
    store = InMemoryEventStore()
    store.append(tenant_id="tenant-a", user_id="u1", event_type="alpha", payload={})
    store.append(tenant_id="tenant-a", user_id="u2", event_type="beta", payload={})
    assert list(store.latest_events(tenant_id="tenant-a", event_type="missing", limit=10)) == []
    assert list(store.iter_events(tenant_id="tenant-a", user_id="u1", event_type="beta", limit=10)) == []
    assert len(list(store.iter_events(tenant_id="tenant-a", limit=10))) == 2
