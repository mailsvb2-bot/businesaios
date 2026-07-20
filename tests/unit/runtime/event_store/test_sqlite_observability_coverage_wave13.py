from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from runtime.platform.event_store import _sqlite_analytics as analytics
from runtime.platform.event_store.sqlite_perf_reporter import (
    Interaction,
    guess_label_from_snapshot_bytes,
    load_interactions,
    percentile,
    render_report,
)


def _events_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE events (event_id TEXT PRIMARY KEY, tenant_id TEXT, user_id TEXT, "
        "source TEXT, event_type TEXT, timestamp_ms INTEGER, decision_id TEXT, "
        "correlation_id TEXT, payload_json TEXT)"
    )
    return db


def _insert(db, eid, tenant, user, event_type, ts, payload):
    db.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, tenant, user, "test", event_type, ts, None, None, json.dumps(payload)),
    )


def test_payload_like_is_strictly_tenant_scoped(tmp_path: Path) -> None:
    db = _events_db(tmp_path / "events.db")
    _insert(db, "1", "tenant-a", "same-user", "sale", 10, {"kind": "premium"})
    _insert(db, "2", "tenant-b", "other-user", "sale", 10, {"kind": "premium"})
    _insert(db, "3", "tenant-a", "system", "sale", 10, {"kind": "premium"})
    db.commit()

    assert analytics.count_events_payload_like(
        db, tenant_id="tenant-a", event_type="sale", payload_substring="premium", end_ms=10
    ) == 2
    assert analytics.count_distinct_users_payload_like(
        db, tenant_id="tenant-a", event_type="sale", payload_substring="premium", end_ms=10
    ) == 1
    with pytest.raises(ValueError):
        analytics.count_events_payload_like(
            db, tenant_id=" ", event_type="sale", payload_substring="premium"
        )


def test_perf_reporter_keeps_same_correlation_key_isolated_by_tenant(tmp_path: Path) -> None:
    events_path = tmp_path / "events.db"
    db = _events_db(events_path)
    snapshots_path = tmp_path / "snapshots.db"
    snapshots = sqlite3.connect(snapshots_path)
    snapshots.execute("CREATE TABLE snapshots (snapshot_id TEXT PRIMARY KEY, canonical_bytes BLOB)")
    snapshots.executemany(
        "INSERT INTO snapshots VALUES (?,?)",
        [
            ("sa", json.dumps({"session": {"command": "/tenant-a"}}).encode()),
            ("sb", json.dumps({"session": {"command": "/tenant-b"}}).encode()),
        ],
    )
    snapshots.commit()
    snapshots.close()

    _insert(db, "d1", "tenant-a", "u", "decision_issued", 100, {"correlation_key": "same", "snapshot_id": "sa"})
    _insert(db, "d2", "tenant-b", "u", "decision_issued", 100, {"correlation_key": "same", "snapshot_id": "sb"})
    _insert(db, "l1", "tenant-a", "u", "latency_span", 101, {"correlation_key": "same", "stage": "router", "duration_ms": 10})
    _insert(db, "l2", "tenant-b", "u", "latency_span", 101, {"correlation_key": "same", "stage": "router", "duration_ms": 20})
    _insert(db, "bad-bool", "tenant-a", "u", "latency_span", 101, {"correlation_key": "same", "stage": "router", "duration_ms": True})
    _insert(db, "bad-neg", "tenant-a", "u", "latency_span", 101, {"correlation_key": "same", "stage": "router", "duration_ms": -100})
    db.commit()
    db.close()

    all_rows = sorted(load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path)), key=lambda x: x.tenant_id)
    assert [(r.tenant_id, r.label, r.totals["router"]) for r in all_rows] == [
        ("tenant-a", "cmd:/tenant-a", 10),
        ("tenant-b", "cmd:/tenant-b", 20),
    ]
    scoped = load_interactions(events_db=str(events_path), snapshots_db=str(snapshots_path), tenant_id="tenant-a")
    assert len(scoped) == 1 and scoped[0].tenant_id == "tenant-a"


def test_label_percentile_and_report_edges() -> None:
    assert percentile([], 50) == 0
    assert percentile([1, 9], 0) == 1
    assert percentile([1, 9], 100) == 9
    assert percentile([0, 10], 50) == 5
    assert guess_label_from_snapshot_bytes(b"bad") == "unknown"
    assert guess_label_from_snapshot_bytes(json.dumps({"session": {"is_callback": True, "callback_data": " ok "}}).encode()) == "cb:ok"
    assert guess_label_from_snapshot_bytes(json.dumps({"session": {"command": "/start", "text": "x" * 50}}).encode()).endswith("...")

    report = render_report(
        interactions=[Interaction("c", "button", {"router": 1, "decide_total": 2, "execute_total": 3, "telegram_api": 4})],
        top_n=0,
    )
    assert "button" in report and "telegram" in report
