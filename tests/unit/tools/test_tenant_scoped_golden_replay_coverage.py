from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tools import tenant_scoped_golden_replay as replay


def test_normalize_event_and_hash_are_stable() -> None:
    event = replay._normalize_event(
        {
            "event_type": "clicked",
            "timestamp_ms": "123",
            "payload": {"x": 1},
            "source": None,
            "user_id": 42,
            "tenant_id": "tenant",
        }
    )

    assert event == {
        "event_type": "clicked",
        "timestamp_ms": 123,
        "payload": {"x": 1},
        "source": "",
        "user_id": "42",
        "tenant_id": "tenant",
    }
    assert replay._normalize_event({"payload": "bad"})["payload"] == {}
    assert replay._sha256_json({"b": 2, "a": 1}) == replay._sha256_json({"a": 1, "b": 2})


def test_load_and_write_golden_roundtrip(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert replay._load_golden(str(missing)) == {"schema_version": 1, "cases": {}}

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version": 2, "cases": {}}', encoding="utf-8")
    try:
        replay._load_golden(str(invalid))
    except SystemExit as exc:
        assert "unsupported golden schema_version" in str(exc)
    else:
        raise AssertionError("expected SystemExit for invalid schema")

    malformed_cases = tmp_path / "malformed_cases.json"
    malformed_cases.write_text('{"schema_version": 1, "cases": []}', encoding="utf-8")
    assert replay._load_golden(str(malformed_cases)) == {"schema_version": 1, "cases": {}}

    out = tmp_path / "nested/golden.json"
    replay._write_golden(str(out), {"schema_version": 1, "cases": {"case": {"hash": "x"}}})
    assert json.loads(out.read_text(encoding="utf-8"))["cases"]["case"]["hash"] == "x"


def test_pick_user_and_extract_trace_with_fake_store(tmp_path: Path, monkeypatch) -> None:
    class FakeStore:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def __enter__(self) -> FakeStore:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def recent_user_ids(self, **_kwargs: object) -> list[tuple[str, int]]:
            return [("user-b", 5000)]

        def iter_events(self, **_kwargs: object) -> list[dict[str, Any]]:
            return [
                {"event_type": "later", "timestamp_ms": 5000, "payload": {}, "tenant_id": "tenant", "user_id": "user-b"},
                {"event_type": "earlier", "timestamp_ms": 4500, "payload": {}, "tenant_id": "tenant", "user_id": "user-b"},
            ]

    monkeypatch.setattr(replay, "SqliteEventStore", FakeStore)
    monkeypatch.setattr(replay, "normalize_tenant_id", lambda value: str(value).strip().lower())

    spec = replay.pick_user_and_window(
        db_path=str(tmp_path / "events.db"),
        tenant_id=" Tenant ",
        window_ms=1000,
        max_users=50000,
        event_limit=999999,
    )

    assert spec.tenant_id == "tenant"
    assert spec.user_id == "user-b"
    assert spec.start_ms == 4000
    assert spec.end_ms == 5000
    assert spec.event_limit == 5000

    limited = replay.TenantScopedReplaySpec(
        tenant_id="tenant",
        user_id="user-b",
        start_ms=0,
        end_ms=9999,
        window_ms=1,
        event_limit=1,
    )
    trace = replay.extract_trace(db_path=str(tmp_path / "events.db"), spec=limited)

    assert [item["event_type"] for item in trace] == ["later"]


def test_pick_user_rejects_missing_tenant_and_empty_candidates(tmp_path: Path, monkeypatch) -> None:
    class EmptyStore:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def __enter__(self) -> EmptyStore:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def recent_user_ids(self, **_kwargs: object) -> list[tuple[str, int]]:
            return []

    monkeypatch.setattr(replay, "SqliteEventStore", EmptyStore)
    monkeypatch.setattr(replay, "normalize_tenant_id", lambda value: str(value).strip())

    try:
        replay.pick_user_and_window(db_path=str(tmp_path / "events.db"), tenant_id="", window_ms=1)
    except SystemExit as exc:
        assert "tenant_id is required" in str(exc)
    else:
        raise AssertionError("expected tenant_id SystemExit")

    try:
        replay.pick_user_and_window(db_path=str(tmp_path / "events.db"), tenant_id="tenant", window_ms=1)
    except SystemExit as exc:
        assert "no users found" in str(exc)
    else:
        raise AssertionError("expected empty candidate SystemExit")


def test_replay_trace_uses_behavioral_state_builder(monkeypatch) -> None:
    class FakeBuilder:
        def build(self, trace: list[dict[str, Any]], product: dict[str, Any], tenant_id: str, safe_mode: bool) -> dict[str, Any]:
            return {
                "event_count": len(trace),
                "product": product,
                "tenant_id": tenant_id,
                "safe_mode": safe_mode,
            }

    monkeypatch.setattr(replay, "BehavioralStateBuilder", FakeBuilder)

    result = replay.replay_trace(
        trace=[{"event_type": "x"}],
        tenant_id="tenant",
        product={"sku": "1"},
        safe_mode=True,
    )

    assert result == {
        "event_count": 1,
        "product": {"sku": "1"},
        "tenant_id": "tenant",
        "safe_mode": True,
    }


def test_write_helpers_and_main_freeze_golden(tmp_path: Path, monkeypatch) -> None:
    trace_path = tmp_path / "trace.json"
    snapshot_path = tmp_path / "snapshot.json"
    meta_path = tmp_path / "meta.json"
    hash_path = tmp_path / "snapshot.sha256"
    golden_path = tmp_path / "golden.json"

    spec = replay.TenantScopedReplaySpec(
        tenant_id="tenant",
        user_id="user",
        start_ms=1,
        end_ms=2,
        window_ms=1,
        event_limit=10,
    )

    monkeypatch.setattr(replay, "pick_user_and_window", lambda **_kwargs: spec)
    monkeypatch.setattr(replay, "extract_trace", lambda **_kwargs: [{"event_type": "x", "timestamp_ms": 2}])
    monkeypatch.setattr(replay, "replay_trace", lambda **_kwargs: {"state": "ok"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tenant_scoped_golden_replay",
            "--db",
            str(tmp_path / "events.db"),
            "--tenant",
            "tenant",
            "--safe-mode",
            "--freeze-golden",
            "--golden-file",
            str(golden_path),
            "--golden-case",
            "case-a",
            "--out-trace",
            str(trace_path),
            "--out-snapshot",
            str(snapshot_path),
            "--out-meta",
            str(meta_path),
            "--out-hash",
            str(hash_path),
        ],
    )

    assert replay.main() == 0

    assert json.loads(trace_path.read_text(encoding="utf-8"))[0]["event_type"] == "x"
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {"state": "ok"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["tenant_id"] == "tenant"
    assert hash_path.read_text(encoding="utf-8").strip() == meta["snapshot_sha256"]

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert golden["cases"]["case-a"]["snapshot_sha256"] == meta["snapshot_sha256"]
