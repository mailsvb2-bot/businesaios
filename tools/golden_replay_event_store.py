from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from core.behavior.behavioral_state_builder import BehavioralStateBuilder


def _normalize_event(e: dict[str, Any]) -> dict[str, Any]:
    # Ensure stable keys and shapes for replay.
    out = {
        "event_type": str(e.get("event_type") or ""),
        "timestamp_ms": int(e.get("timestamp_ms") or 0),
        "payload": e.get("payload") if isinstance(e.get("payload"), dict) else {},
        "source": str(e.get("source") or ""),
        "user_id": str(e.get("user_id") or ""),
        "tenant_id": str(e.get("tenant_id") or ""),
    }
    return out


def extract_trace(*, db_path: str, tenant_id: str, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    with SqliteEventStore(db_path) as es:
        for ev in es.iter_events(tenant_id=str(tenant_id), user_id=str(user_id), start_ms=0, end_ms=None):
            trace.append(_normalize_event(ev))
    trace = sorted(trace, key=lambda x: int(x.get("timestamp_ms") or 0))
    if limit and len(trace) > int(limit):
        trace = trace[-int(limit) :]
    return trace


def replay_trace(*, trace: list[dict[str, Any]], product: dict[str, Any] | None = None, tenant_id: str = "default", safe_mode: bool = False) -> dict[str, Any]:
    b = BehavioralStateBuilder()
    return dict(b.build(trace, product=product or {}, tenant_id=str(tenant_id), safe_mode=bool(safe_mode)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to sqlite events db")
    ap.add_argument("--tenant", default="default")
    ap.add_argument("--user", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out-trace", default="artifacts/golden_trace.json")
    ap.add_argument("--out-snapshot", default="artifacts/golden_snapshot.json")
    ap.add_argument("--safe-mode", action="store_true")
    args = ap.parse_args()

    trace = extract_trace(db_path=args.db, tenant_id=args.tenant, user_id=args.user, limit=args.limit)
    snap = replay_trace(trace=trace, product={}, tenant_id=args.tenant, safe_mode=bool(args.safe_mode))

    with open(args.out_trace, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, sort_keys=True, indent=2)
    with open(args.out_snapshot, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, sort_keys=True, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
