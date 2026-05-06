from __future__ import annotations

"""Aggregate latency_span into a Top-10 slowest buttons table.

Reads directly from event_store (SQLite events.db + snapshots.db) and prints a
compact report.

Usage:
  python -m analytics.latency_top10
  python -m analytics.latency_top10 --data-dir runtime/entrypoints/data --top 10 --since-ms 0
"""

import argparse
import os
from typing import Optional


def _int_or_none(v: str | None) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Top slow buttons from latency_span")
    ap.add_argument("--data-dir", default=None, help="Directory with events.db and snapshots.db")
    ap.add_argument("--events-db", default=None, help="Path to events.db (overrides --data-dir)")
    ap.add_argument("--snapshots-db", default=None, help="Path to snapshots.db (overrides --data-dir)")
    ap.add_argument("--top", default="10", help="How many rows to print")
    ap.add_argument("--since-ms", default=None, help="Filter events newer than timestamp_ms")
    args = ap.parse_args()

    from runtime.platform.event_store.sqlite_perf_reporter import default_paths_from_env, load_interactions, render_report

    data_dir = args.data_dir
    if args.events_db and args.snapshots_db:
        events_db = str(args.events_db)
        snapshots_db = str(args.snapshots_db)
    else:
        events_db, snapshots_db = default_paths_from_env(data_dir=data_dir)

    if not os.path.exists(events_db):
        raise SystemExit(f"events.db not found: {events_db}")
    if not os.path.exists(snapshots_db):
        raise SystemExit(f"snapshots.db not found: {snapshots_db}")

    since_ms = _int_or_none(args.since_ms)
    try:
        top_n = max(1, int(args.top))
    except Exception:
        top_n = 10

    interactions = load_interactions(events_db=events_db, snapshots_db=snapshots_db, since_ms=since_ms)
    print(render_report(interactions=interactions, top_n=top_n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
