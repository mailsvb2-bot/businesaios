from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tools import golden_replay_event_store as replay


def test_normalize_event_is_stable_and_defensive() -> None:
    assert replay._normalize_event(
        {
            "event_type": "opened",
            "timestamp_ms": "123",
            "payload": {"x": 1},
            "source": None,
            "user_id": 42,
            "tenant_id": "tenant",
        }
    ) == {
        "event_type": "opened",
        "timestamp_ms": 123,
        "payload": {"x": 1},
        "source": "",
        "user_id": "42",
        "tenant_id": "tenant",
    }

    assert replay._normalize_event({"payload": "bad"}) == {
        "event_type": "",
        "timestamp_ms": 0,
        "payload": {},
        "source": "",
        "user_id": "",
        "tenant_id": "",
    }


def test_extract_trace_sorts_and_limits_with_fake_store(tmp_path: Path, monkeypatch) -> None:
    class FakeStore:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def __enter__(self) -> FakeStore:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def iter_events(self, **_kwargs: object) -> list[dict[str, Any]]:
            return [
                {"event_type": "late", "timestamp_ms": 300, "payload": {"n": 3}},
                {"event_type": "early", "timestamp_ms": 100, "payload": {"n": 1}},
                {"event_type": "middle", "timestamp_ms": 200, "payload": {"n": 2}},
            ]

    monkeypatch.setattr(replay, "SqliteEventStore", FakeStore)

    trace = replay.extract_trace(
        db_path=str(tmp_path / "events.db"),
        tenant_id="tenant",
        user_id="user",
        limit=2,
    )

    assert [item["event_type"] for item in trace] == ["middle", "late"]


def test_replay_trace_uses_behavioral_state_builder(monkeypatch) -> None:
    class FakeBuilder:
        def build(
            self,
            trace: list[dict[str, Any]],
            product: dict[str, Any],
            tenant_id: str,
            safe_mode: bool,
        ) -> dict[str, Any]:
            return {
                "event_count": len(trace),
                "product": product,
                "tenant_id": tenant_id,
                "safe_mode": safe_mode,
            }

    monkeypatch.setattr(replay, "BehavioralStateBuilder", FakeBuilder)

    assert replay.replay_trace(
        trace=[{"event_type": "x"}],
        product={"sku": "1"},
        tenant_id="tenant",
        safe_mode=True,
    ) == {
        "event_count": 1,
        "product": {"sku": "1"},
        "tenant_id": "tenant",
        "safe_mode": True,
    }


def test_main_writes_trace_and_snapshot(tmp_path: Path, monkeypatch) -> None:
    trace_path = tmp_path / "trace.json"
    snapshot_path = tmp_path / "snapshot.json"

    monkeypatch.setattr(
        replay,
        "extract_trace",
        lambda **_kwargs: [{"event_type": "x", "timestamp_ms": 1, "payload": {}}],
    )
    monkeypatch.setattr(
        replay,
        "replay_trace",
        lambda **_kwargs: {"state": "ok"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golden_replay_event_store",
            "--db",
            str(tmp_path / "events.db"),
            "--tenant",
            "tenant",
            "--user",
            "user",
            "--limit",
            "5",
            "--out-trace",
            str(trace_path),
            "--out-snapshot",
            str(snapshot_path),
            "--safe-mode",
        ],
    )

    assert replay.main() == 0
    assert json.loads(trace_path.read_text(encoding="utf-8"))[0]["event_type"] == "x"
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {"state": "ok"}
