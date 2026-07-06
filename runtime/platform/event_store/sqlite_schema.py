"""SQLite DDL and migration helpers for SqliteEventStore.

Extracted from sqlite_event_store.py to eliminate god-module.
"""

from __future__ import annotations

import sqlite3

from observability.platform.observability.silent import swallow

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL_EVENTS = (
    "CREATE TABLE IF NOT EXISTS events ("
    "event_id TEXT PRIMARY KEY, "
    "tenant_id TEXT NOT NULL DEFAULT 'legacy', "
    "user_id TEXT, "
    "source TEXT NOT NULL, "
    "event_type TEXT NOT NULL, "
    "timestamp_ms INTEGER NOT NULL, "
    "decision_id TEXT, "
    "correlation_id TEXT, "
    "payload_json TEXT NOT NULL)"
)

_DDL_EVENT_COUNTERS = (
    "CREATE TABLE IF NOT EXISTS event_counters ("
    "event_type TEXT NOT NULL, "
    "user_id TEXT NOT NULL, "
    "cnt INTEGER NOT NULL, "
    "last_ts_ms INTEGER NOT NULL, "
    "PRIMARY KEY (event_type, user_id))"
)

_DDL_USER_STATE = (
    "CREATE TABLE IF NOT EXISTS user_state ("
    "tenant_id TEXT NOT NULL, "
    "user_id TEXT NOT NULL, "
    "state_json TEXT NOT NULL, "
    "updated_at_ms INTEGER NOT NULL, "
    "PRIMARY KEY (tenant_id, user_id))"
)

_DDL_USER_FEATURES_DAILY = (
    "CREATE TABLE IF NOT EXISTS user_features_daily ("
    "tenant_id TEXT NOT NULL, "
    "user_id TEXT NOT NULL, "
    "day_key TEXT NOT NULL, "
    "features_json TEXT NOT NULL, "
    "created_at_ms INTEGER NOT NULL, "
    "PRIMARY KEY (tenant_id, user_id, day_key))"
)

_DDL_BANDIT_ARMS = (
    "CREATE TABLE IF NOT EXISTS bandit_arms ("
    "tenant_id TEXT NOT NULL, "
    "arm TEXT NOT NULL, "
    "alpha REAL NOT NULL DEFAULT 1.0, "
    "beta REAL NOT NULL DEFAULT 1.0, "
    "last_updated_at_ms INTEGER NOT NULL, "
    "PRIMARY KEY (tenant_id, arm))"
)

_DDL_JOB_LOCKS = (
    "CREATE TABLE IF NOT EXISTS job_locks ("
    "tenant_id TEXT NOT NULL, "
    "job_key TEXT NOT NULL, "
    "locked_at_ms INTEGER NOT NULL, "
    "PRIMARY KEY (tenant_id, job_key))"
)

_DDL_SETTINGS = (
    "CREATE TABLE IF NOT EXISTS settings ("
    "tenant_id TEXT NOT NULL, "
    "key TEXT NOT NULL, "
    "value_json TEXT NOT NULL, "
    "updated_at_ms INTEGER NOT NULL, "
    "PRIMARY KEY (tenant_id, key))"
)


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

def init_schema(db: sqlite3.Connection) -> None:
    """Create all tables and indexes. Safe to call on every open."""
    db.execute(_DDL_EVENTS)
    _maybe_add_tenant_id_column(db)
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp_ms)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, timestamp_ms)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, timestamp_ms)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_user_ts ON events(event_type, user_id, timestamp_ms)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_user_ts ON events(tenant_id, user_id, timestamp_ms)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_type_ts ON events(tenant_id, event_type, timestamp_ms)")

    db.execute(_DDL_EVENT_COUNTERS)
    db.execute("CREATE INDEX IF NOT EXISTS idx_counters_last_ts ON event_counters(last_ts_ms)")

    db.execute(_DDL_USER_STATE)
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_state_updated ON user_state(updated_at_ms)")

    db.execute(_DDL_USER_FEATURES_DAILY)
    db.execute("CREATE INDEX IF NOT EXISTS idx_features_user_day ON user_features_daily(user_id, day_key)")

    db.execute(_DDL_BANDIT_ARMS)
    db.execute(_DDL_JOB_LOCKS)
    db.execute(_DDL_SETTINGS)
    db.execute("CREATE INDEX IF NOT EXISTS idx_settings_updated ON settings(updated_at_ms)")
    db.commit()


def _maybe_add_tenant_id_column(db: sqlite3.Connection) -> None:
    """Migration: add tenant_id column to older schemas that lack it."""
    try:
        cols = [str(r[1]) for r in db.execute("PRAGMA table_info(events)").fetchall()]
        if "tenant_id" not in {c.lower() for c in cols}:
            db.execute("ALTER TABLE events ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'legacy'")
    except Exception:
        swallow(__name__, "sqlite_schema.migrate_tenant_id")


def backfill_legacy_tenant_ids(db: sqlite3.Connection) -> None:
    """Safety migration: NULL/blank tenant_id → 'legacy'. Best-effort."""
    try:
        db.execute("UPDATE events SET tenant_id='legacy' WHERE tenant_id IS NULL OR TRIM(tenant_id)=''")
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            swallow(__name__, "sqlite_schema.backfill_rollback")
