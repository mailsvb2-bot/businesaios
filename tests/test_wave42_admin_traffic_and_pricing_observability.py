from __future__ import annotations

import json
from pathlib import Path

from core.admin.read_models.traffic import demo_summary, funnel2_report, users_today
from runtime.admin_pricing import execute_plan_price_update
from runtime.admin_state_support import build_pricing_change_payload


class _Store:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id: str, start_ms: int = 0, event_type: str | None = None):
        for ev in self._events:
            if int(ev.get("ts_ms", 0)) < int(start_ms):
                continue
            if event_type is not None and str(ev.get("event_type")) != str(event_type):
                continue
            yield dict(ev)


def test_traffic_read_models_respect_explicit_now_ms() -> None:
    day_start = 1_699_920_000_000  # exact UTC midnight boundary for stable start-of-day checks
    store = _Store(
        [
            {"ts_ms": day_start - 2 * 24 * 3600 * 1000, "user_id": "old", "event_type": "audio_sent", "payload": {"path": "home"}},
            {"ts_ms": day_start + 1000, "user_id": "u1", "event_type": "audio_sent", "payload": {"path": "work"}},
            {"ts_ms": day_start + 2000, "user_id": "u2", "event_type": "tariffs_viewed", "payload": {}},
        ]
    )
    explicit_now_ms = day_start + 10_000
    assert users_today(store, now_ms=explicit_now_ms) == 2
    assert demo_summary(store, days=1, now_ms=explicit_now_ms) == {"sent_work": 1, "sent_home": 0, "users": 1}
    report = funnel2_report(store, days=1, now_ms=explicit_now_ms)
    assert report["start_ms"] == explicit_now_ms - 24 * 3600 * 1000
    assert report["counts"]["tariffs_viewed"] == 1


def test_execute_plan_price_update_reports_override_observability(tmp_path: Path) -> None:
    plans_path = tmp_path / "plans.json"
    plans_path.write_text(json.dumps([{"plan_id": 7, "price": 100}]), encoding="utf-8")
    override_path = tmp_path / "pricing_version_override.txt"

    result = execute_plan_price_update(
        plan_id=7,
        new_price=150,
        pricing_version="v2.1",
        plans_path=plans_path,
        override_path=override_path,
    )

    assert result["override_persisted"] is True
    assert result["override_path"] == str(override_path)
    assert override_path.read_text(encoding="utf-8").strip() == "v2.1"


def test_build_pricing_change_payload_is_canonical() -> None:
    payload = build_pricing_change_payload(
        request_id="req-1",
        plan_id=11,
        new_price=777,
        pricing_version="v9",
        requested_by="admin-1",
        reason="manual review",
        plans_path="data/plans.json",
        override_path="data/override.txt",
        override_persisted=True,
    )
    assert payload == {
        "request_id": "req-1",
        "plan_id": 11,
        "new_price": 777,
        "pricing_version": "v9",
        "requested_by": "admin-1",
        "reason": "manual review",
        "plans_path": "data/plans.json",
        "override_path": "data/override.txt",
        "override_persisted": True,
    }
