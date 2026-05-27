from __future__ import annotations

import hashlib
import json
import time

from core.behavior.behavioral_state_builder import BehavioralStateBuilder
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def _stable_hash(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_golden_replay_real_event_store_trace(tmp_path):
    # "Real" trace: events are written through the actual SqliteEventStore,
    # then read back via iter_events and replayed.
    db_path = str(tmp_path / "events.db")
    tenant_id = "default"
    user_id = "u1"

    now = int(time.time() * 1000)
    events = [
        {"tenant_id": tenant_id, "user_id": user_id, "source": "telegram", "event_type": "ui_click", "timestamp_ms": now + 1, "payload": {"button_id": "start"}},
        {"tenant_id": tenant_id, "user_id": user_id, "source": "telegram", "event_type": "offer_shown", "timestamp_ms": now + 2, "payload": {"offer_id": "offer_30_a", "funnel_stage": "consideration"}},
        {"tenant_id": tenant_id, "user_id": user_id, "source": "telegram", "event_type": "offer_clicked", "timestamp_ms": now + 3, "payload": {"offer_id": "offer_30_a", "funnel_stage": "decision"}},
        {"tenant_id": tenant_id, "user_id": user_id, "source": "payments", "event_type": "purchase_attempt", "timestamp_ms": now + 4, "payload": {"offer_id": "offer_30_a", "amount_rub": 2990}},
        {"tenant_id": tenant_id, "user_id": user_id, "source": "payments", "event_type": "purchase_success", "timestamp_ms": now + 5, "payload": {"offer_id": "offer_30_a", "amount_rub": 2990}},
    ]

    with SqliteEventStore(db_path) as es:
        for e in events:
            es.append_event(e)

    # Read back the trace from event_store
    trace = []
    with SqliteEventStore(db_path) as es:
        for e in es.iter_events(tenant_id=tenant_id, user_id=user_id, start_ms=0, end_ms=None):
            trace.append(
                {
                    "event_type": str(e.get("event_type") or ""),
                    "timestamp_ms": int(e.get("timestamp_ms") or 0),
                    "payload": e.get("payload") if isinstance(e.get("payload"), dict) else {},
                }
            )
    trace = sorted(trace, key=lambda x: int(x.get("timestamp_ms") or 0))

    b = BehavioralStateBuilder()
    snap1 = dict(b.build(trace, product={}, tenant_id=tenant_id, safe_mode=True))
    snap2 = dict(b.build(trace, product={}, tenant_id=tenant_id, safe_mode=True))

    # Determinism check (catches "second lines"/divergences).
    assert snap1 == snap2

    # Golden hash: if behavior/operator logic changes, this will flag it loudly.
    assert _stable_hash(snap1) == "d32d8e8822e0052b31482e7006efc06a2ac26e9528007b7d2a3f0ab98d991513"
