from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from runtime.platform.event_store import _sqlite_analytics as compatibility_analytics
from runtime.platform.event_store import sqlite_read_queries as analytics
from runtime.platform.event_store.sqlite_perf_reporter import (
    Interaction,
    default_paths_from_env,
    guess_label_from_snapshot_bytes,
    load_interactions,
    open_ro,
    percentile,
    render_report,
)


def _events_db(path: Path | str = ":memory:") -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE events (event_id TEXT PRIMARY KEY, tenant_id TEXT, user_id TEXT, "
        "source TEXT, event_type TEXT, timestamp_ms INTEGER, decision_id TEXT, "
        "correlation_id TEXT, payload_json TEXT)"
    )
    db.execute(
        "CREATE TABLE event_counters (event_type TEXT NOT NULL, user_id TEXT NOT NULL, "
        "cnt INTEGER NOT NULL, last_ts_ms INTEGER NOT NULL, PRIMARY KEY(event_type,user_id))"
    )
    return db


def _insert(db, eid, tenant, user, event_type, ts, payload, *, raw: bool = False):
    payload_json = payload if raw else json.dumps(payload)
    db.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, tenant, user, "test", event_type, ts, None, None, payload_json),
    )


def _modern_snapshots(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE snapshots (snapshot_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, "
        "canonical_bytes BLOB NOT NULL)"
    )
    return db


def test_compatibility_module_is_not_a_second_query_implementation() -> None:
    assert compatibility_analytics.count_events is analytics.count_events
    assert compatibility_analytics.count_distinct_users is analytics.count_distinct_users
    assert compatibility_analytics.sum_event_payload_int is analytics.sum_event_payload_int
    assert compatibility_analytics.count_events_payload_like is analytics.count_events_payload_like
    assert compatibility_analytics._req_tenant(" tenant-a ") == "tenant-a"
    with pytest.raises(ValueError):
        compatibility_analytics._req_tenant(" ")


def test_canonical_counter_matches_writer_schema() -> None:
    db = _events_db()
    db.executemany(
        "INSERT INTO event_counters VALUES (?,?,?,?)",
        [("sale", "__all__", 7, 10), ("sale", "u1", 3, 10)],
    )
    assert analytics.get_counter(db, event_type="sale") == 7
    assert analytics.get_counter(db, event_type="sale", user_id="u1") == 3
    assert analytics.get_counter(db, event_type="missing") == 0


def test_canonical_query_surface_and_literal_payload_matching() -> None:
    db = _events_db()
    now = int(time.time() * 1000)
    day = 86_400_000
    _insert(db, "1", "tenant-a", "u1", "sale", now - day, {"amount": 2, "tag": "100%_done"})
    _insert(db, "2", "tenant-a", "u1", "sale", now, {"amount": "3", "tag": "other"})
    _insert(db, "3", "tenant-a", "u2", "view", now - 10, {"amount": "bad", "tag": "100XXdone"})
    _insert(db, "4", "tenant-a", "system", "sale", now - 5, {"amount": 5, "tag": "100%_done"})
    _insert(db, "5", "tenant-a", None, "sale", now - 4, {"amount": 8, "tag": "100%_done"})
    _insert(db, "6", "tenant-b", "u9", "sale", now, {"amount": 99, "tag": "100%_done"})
    db.commit()

    rows = list(analytics.iter_events(db, tenant_id="tenant-a", event_types=["sale", "sale", "view"], limit=20))
    assert [row["event_id"] for row in rows] == ["1", "3", "4", "5", "2"]
    assert [row["event_id"] for row in analytics.iter_events(db, tenant_id="tenant-a", event_type="view")] == ["3"]
    assert [row["event_id"] for row in analytics.iter_events(db, tenant_id="tenant-a", user_id="u1")] == ["1", "2"]
    assert analytics.latest_event(db, tenant_id="tenant-a", user_id="u1", event_types=["sale"])["event_id"] == "2"
    assert analytics.latest_event(db, tenant_id="tenant-a", event_types=["view"])["event_id"] == "3"
    assert analytics.latest_event(db, tenant_id="tenant-a")["event_id"] == "2"
    assert analytics.latest_event(db, tenant_id="missing") is None
    assert [row["event_id"] for row in analytics.latest_events(db, tenant_id="tenant-a", event_type="sale", limit=2)] == ["2", "5"]

    assert analytics.count_distinct_users(db, tenant_id="tenant-a", start_ms=0) == 2
    assert analytics.count_distinct_users(db, tenant_id="tenant-a", start_ms=0, exclude_system=False) == 3
    assert analytics.count_distinct_users(db, tenant_id="tenant-a", start_ms=0, event_type="sale") == 1
    assert analytics.recent_user_ids(db, tenant_id="tenant-a", limit=10) == [("u1", now), ("u2", now - 10)]
    assert analytics.recent_user_ids(db, tenant_id="tenant-a", limit=10, exclude_system=False)[0] == ("u1", now)
    assert analytics.count_events(db, tenant_id="tenant-a", event_type="sale") == 4
    assert analytics.count_events(db, tenant_id="tenant-a", event_type="sale", user_id="u1") == 2
    assert analytics.count_events(db, tenant_id="missing", event_type="sale") == 0
    assert analytics.sum_event_payload_int(db, tenant_id="tenant-a", event_type="sale", user_id="u1", field="amount") == 5
    assert analytics.sum_event_payload_int(db, tenant_id="tenant-a", event_type="view", field="amount") == 0
    assert analytics.count_active_users_min_days(db, tenant_id="tenant-a", lookback_days=3, min_active_days=2) == 1

    assert analytics.count_events_payload_like(
        db,
        tenant_id="tenant-a",
        event_type="sale",
        payload_substring="100%_done",
    ) == 3
    assert analytics.count_distinct_users_payload_like(
        db,
        tenant_id="tenant-a",
        event_type="sale",
        payload_substring="100%_done",
    ) == 1
    assert analytics.count_events_payload_like(
        db,
        tenant_id="tenant-a",
        event_type="view",
        payload_substring="100%_done",
    ) == 0


def test_perf_reporter_tenant_binding_latest_snapshot_and_invalid_evidence(tmp_path: Path) -> None:
    events_path = tmp_path / "events.db"
    db = _events_db(events_path)
    snapshots_path = tmp_path / "snapshots.db"
    snapshots = _modern_snapshots(snapshots_path)
    snapshots.executemany(
        "INSERT INTO snapshots VALUES (?,?,?)",
        [
            ("sa-old", "tenant-a", json.dumps({"session": {"command": "/old"}}).encode()),
            ("sa-new", "tenant-a", json.dumps({"session": {"command": "/new"}}).encode()),
            ("sb", "tenant-b", json.dumps({"session": {"command": "/tenant-b"}}).encode()),
        ],
    )
    snapshots.commit()
    snapshots.close()

    _insert(db, "d-old", "tenant-a", "u", "decision_issued", 100, {"correlation_key": " same ", "snapshot_id": "sa-old"})
    _insert(db, "d-new", "tenant-a", "u", "decision_issued", 200, {"correlation_key": "same", "snapshot_id": "sa-new"})
    _insert(db, "d-cross", "tenant-a", "u", "decision_issued", 200, {"correlation_key": "cross", "snapshot_id": "sb"})
    _insert(db, "d-b", "tenant-b", "u", "decision_issued", 100, {"correlation_key": "same", "snapshot_id": "sb"})
    _insert(db, "bad-json-decision", "tenant-a", "u", "decision_issued", 100, "{", raw=True)
    _insert(db, "list-decision", "tenant-a", "u", "decision_issued", 100, [1])
    _insert(db, "bad-decision", "tenant-a", "u", "decision_issued", 100, {"correlation_key": 1, "snapshot_id": None})

    _insert(db, "l1", "tenant-a", "u", "latency_span", 201, {"correlation_key": "same", "stage": "router", "duration_ms": 10})
    _insert(db, "l2", "tenant-a", "u", "latency_span", 202, {"correlation_key": "same", "stage": "execute_total", "duration_ms": 5})
    _insert(db, "l-cross", "tenant-a", "u", "latency_span", 203, {"correlation_key": "cross", "stage": "router", "duration_ms": 7})
    _insert(db, "l-b", "tenant-b", "u", "latency_span", 201, {"correlation_key": "same", "stage": "router", "duration_ms": 20})
    _insert(db, "bad-bool", "tenant-a", "u", "latency_span", 204, {"correlation_key": "same", "stage": "router", "duration_ms": True})
    _insert(db, "bad-neg", "tenant-a", "u", "latency_span", 204, {"correlation_key": "same", "stage": "router", "duration_ms": -100})
    _insert(db, "bad-type", "tenant-a", "u", "latency_span", 204, {"correlation_key": "same", "stage": "router", "duration_ms": "9"})
    _insert(db, "bad-stage", "tenant-a", "u", "latency_span", 204, {"correlation_key": "same", "stage": "other", "duration_ms": 9})
    _insert(db, "bad-key", "tenant-a", "u", "latency_span", 204, {"correlation_key": " ", "stage": "router", "duration_ms": 9})
    _insert(db, "bad-json-latency", "tenant-a", "u", "latency_span", 204, "{", raw=True)
    _insert(db, "list-latency", "tenant-a", "u", "latency_span", 204, [1])
    db.commit()
    db.close()

    all_rows = load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path))
    assert [(r.tenant_id, r.correlation_key, r.label, r.totals["router"]) for r in all_rows] == [
        ("tenant-a", "cross", "unknown", 7),
        ("tenant-a", "same", "cmd:/new", 10),
        ("tenant-b", "same", "cmd:/tenant-b", 20),
    ]
    assert all_rows[1].totals["execute_total"] == 5
    scoped = load_interactions(
        events_db=str(events_path),
        snapshots_db=str(snapshots_path),
        tenant_id="tenant-a",
        since_ms=150,
    )
    assert [(row.correlation_key, row.label) for row in scoped] == [("cross", "unknown"), ("same", "cmd:/new")]
    with pytest.raises(ValueError):
        load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path), tenant_id=" ")
    with pytest.raises(ValueError):
        load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path), since_ms=True)
    with pytest.raises(ValueError):
        load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path), since_ms=-1)


def test_perf_reporter_legacy_snapshot_schema_is_fail_closed_for_modern_tenants(tmp_path: Path) -> None:
    events_path = tmp_path / "events.db"
    db = _events_db(events_path)
    snapshots_path = tmp_path / "snapshots.db"
    snapshots = sqlite3.connect(snapshots_path)
    snapshots.execute("CREATE TABLE snapshots (snapshot_id TEXT PRIMARY KEY, canonical_bytes BLOB)")
    snapshots.execute(
        "INSERT INTO snapshots VALUES (?,?)",
        ("legacy-snapshot", json.dumps({"session": {"text": "legacy label"}}).encode()),
    )
    snapshots.execute("INSERT INTO snapshots VALUES (?,NULL)", ("empty",))
    snapshots.commit()
    snapshots.close()

    _insert(db, "d1", "legacy", "u", "decision_issued", 1, {"correlation_key": "legacy", "snapshot_id": "legacy-snapshot"})
    _insert(db, "d2", "tenant-a", "u", "decision_issued", 1, {"correlation_key": "modern", "snapshot_id": "legacy-snapshot"})
    _insert(db, "d3", "legacy", "u", "decision_issued", 1, {"correlation_key": "empty", "snapshot_id": "empty"})
    _insert(db, "l1", "legacy", "u", "latency_span", 2, {"correlation_key": "legacy", "stage": "router", "duration_ms": 1})
    _insert(db, "l2", "tenant-a", "u", "latency_span", 2, {"correlation_key": "modern", "stage": "router", "duration_ms": 2})
    _insert(db, "l3", "legacy", "u", "latency_span", 2, {"correlation_key": "empty", "stage": "router", "duration_ms": 3})
    db.commit()
    db.close()

    rows = load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path))
    labels = {(row.tenant_id, row.correlation_key): row.label for row in rows}
    assert labels[("legacy", "legacy")] == "text:legacy label"
    assert labels[("tenant-a", "modern")] == "unknown"
    assert labels[("legacy", "empty")] == "unknown"


def test_label_percentile_report_paths_and_read_only_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert percentile([], 50) == 0
    assert percentile([1, 9], 0) == 1
    assert percentile([1, 9], 100) == 9
    assert percentile([7], 50) == 7
    assert percentile([0, 10], 50) == 5
    assert guess_label_from_snapshot_bytes(b"bad") == "unknown"
    assert guess_label_from_snapshot_bytes(json.dumps([1]).encode()) == "unknown"
    assert guess_label_from_snapshot_bytes(json.dumps({"session": "bad"}).encode()) == "unknown"
    assert guess_label_from_snapshot_bytes(
        json.dumps({"session": {"is_callback": True, "callback_data": " ok "}}).encode()
    ) == "cb:ok"
    assert guess_label_from_snapshot_bytes(
        json.dumps({"session": {"command": " /help "}}).encode()
    ) == "cmd:/help"
    assert guess_label_from_snapshot_bytes(
        json.dumps({"session": {"command": "/start", "text": "short\ntext"}}).encode()
    ) == "text:short text"
    assert guess_label_from_snapshot_bytes(
        json.dumps({"session": {"text": "x" * 50}}).encode()
    ).endswith("...")
    assert guess_label_from_snapshot_bytes(json.dumps({"session": {}}).encode()) == "unknown"

    report = render_report(
        interactions=[
            Interaction("c1", "z" * 40, {"router": 1, "decide_total": 2, "execute_total": 3, "telegram_api": 4}),
            Interaction("c2", "fast", {"router": 1, "decide_total": 0, "execute_total": 0, "telegram_api": 0}),
        ],
        top_n=1,
    )
    assert "zzz" in report and "fast" not in report and "1/2/3/4" in report
    full_report = render_report(
        interactions=[Interaction("c", "fast", {stage: 0 for stage in ("router", "decide_total", "execute_total", "telegram_api")})],
        top_n=2,
    )
    assert "fast" in full_report
    assert "TOP buttons" in render_report(interactions=[], top_n=0)

    db_path = tmp_path / "read-only.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE probe (value INTEGER)")
    db.execute("INSERT INTO probe VALUES (1)")
    db.commit()
    db.close()
    with open_ro(str(db_path)) as ro:
        assert ro.execute("SELECT value FROM probe").fetchone()[0] == 1

    assert default_paths_from_env(" /tmp/data ") == ("/tmp/data/events.db", "/tmp/data/snapshots.db")
    monkeypatch.setenv("DATA_DIR", "/env/data")
    assert default_paths_from_env() == ("/env/data/events.db", "/env/data/snapshots.db")
    monkeypatch.delenv("DATA_DIR")
    assert default_paths_from_env()[0].endswith("runtime/entrypoints/data/events.db")
