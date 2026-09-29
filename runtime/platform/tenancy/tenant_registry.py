from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import read_json_or_default
from tenancy.tenant_quota_guard import (
    InMemoryTenantQuotaCounterStore,
    PersistentTenantQuotaCounterStore,
    TenantQuotaCounterState,
    TenantQuotaCounterStore,
    _normalized_state,
    quota_quota_quantity_decimal,
    tenant_quota_counter_store_path,
)

class EventStore(Protocol):
    def append(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: dict[str, Any]) -> None: ...
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 5000) -> Iterable[dict[str, Any]]: ...

@dataclass(frozen=True)
class TenantInfo:
    tenant_id: str
    enabled: bool = True

class TenantRegistry:
    EVT_REG = "tenant_registered"
    EVT_DIS = "tenant_disabled"

    def __init__(self, *, store: EventStore, registry_tenant_id: str = "system"):
        self._store = store
        self._registry_tid = registry_tenant_id

    def register(self, *, tenant_id: str, enabled: bool = True) -> None:
        self._store.append(
            tenant_id=self._registry_tid,
            user_id=None,
            event_type=self.EVT_REG,
            payload={"tenant_id": tenant_id, "enabled": bool(enabled), "ts_iso": datetime.now(UTC).isoformat()},
        )

    def disable(self, *, tenant_id: str) -> None:
        self._store.append(
            tenant_id=self._registry_tid,
            user_id=None,
            event_type=self.EVT_DIS,
            payload={"tenant_id": tenant_id, "ts_iso": datetime.now(UTC).isoformat()},
        )

    def list_active_tenants(self, *, limit: int = 5000) -> list[TenantInfo]:
        disabled = set()
        for ev in self._store.latest_events(tenant_id=self._registry_tid, event_type=self.EVT_DIS, limit=limit):
            tid = str((ev.get("payload") or {}).get("tenant_id") or "").strip()
            if tid:
                disabled.add(tid)

        last: dict[str, TenantInfo] = {}
        for ev in self._store.latest_events(tenant_id=self._registry_tid, event_type=self.EVT_REG, limit=limit):
            p = ev.get("payload") or {}
            tid = str(p.get("tenant_id") or "").strip()
            if not tid:
                continue
            last[tid] = TenantInfo(tenant_id=tid, enabled=bool(p.get("enabled", True)))

        res = [info for tid, info in last.items() if info.enabled and tid not in disabled]
        res.sort(key=lambda x: x.tenant_id)
        return res

SQLITE_SCHEMA_VERSION = 1

def tenant_quota_counter_sqlite_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_QUOTA_COUNTER_SQLITE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_quota_counters.sqlite3"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_quota_counters.sqlite3"

class SQLiteTenantQuotaCounterStore:
    """Production quota-counter backend with cross-process atomic increments."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else tenant_quota_counter_sqlite_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._path), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tenant_quota_counter_meta "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            row = conn.execute(
                "SELECT value FROM tenant_quota_counter_meta WHERE key = ?",
                ("schema_version",),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO tenant_quota_counter_meta(key, value) VALUES (?, ?)",
                    ("schema_version", str(SQLITE_SCHEMA_VERSION)),
                )
            elif int(row[0]) != SQLITE_SCHEMA_VERSION:
                raise RuntimeError("unsupported tenant quota counter schema version")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_quota_counters (
                    tenant_id TEXT NOT NULL,
                    counter_key TEXT NOT NULL,
                    window_key TEXT NOT NULL,
                    used_text TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, counter_key, window_key)
                )
                """
            )

    @staticmethod
    def _decode(row: tuple[object, ...]) -> TenantQuotaCounterState:
        return _normalized_state(
            TenantQuotaCounterState(
                tenant_id=str(row[0]),
                counter_key=str(row[1]),
                window_key=str(row[2]),
                used=quota_quantity_decimal(row[3], name="used"),
                updated_at=datetime.fromisoformat(str(row[4])),
            )
        )

    def get(self, *, tenant_id: str, counter_key: str, window_key: str) -> TenantQuotaCounterState | None:
        tid = require_tenant_id(tenant_id)
        key = str(counter_key).strip()
        window = str(window_key).strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tenant_id, counter_key, window_key, used_text, updated_at "
                "FROM tenant_quota_counters WHERE tenant_id = ? AND counter_key = ? AND window_key = ?",
                (tid, key, window),
            ).fetchone()
        return None if row is None else self._decode(row)

    def save(self, state: TenantQuotaCounterState) -> TenantQuotaCounterState:
        normalized = _normalized_state(state)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tenant_quota_counters(
                    tenant_id, counter_key, window_key, used_text, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, counter_key, window_key)
                DO UPDATE SET used_text = excluded.used_text, updated_at = excluded.updated_at
                """,
                (
                    normalized.tenant_id,
                    normalized.counter_key,
                    normalized.window_key,
                    str(normalized.used),
                    normalized.updated_at.isoformat(),
                ),
            )
        return normalized

    def increment(
        self,
        *,
        tenant_id: str,
        counter_key: str,
        window_key: str,
        amount: Decimal,
        updated_at: datetime,
    ) -> TenantQuotaCounterState:
        tid = require_tenant_id(tenant_id)
        key = str(counter_key).strip()
        window = str(window_key).strip()
        delta = quota_quantity_decimal(amount, name="amount")
        if not key or not window:
            raise ValueError("counter_key and window_key are required")
        if updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT used_text FROM tenant_quota_counters "
                "WHERE tenant_id = ? AND counter_key = ? AND window_key = ?",
                (tid, key, window),
            ).fetchone()
            current = Decimal("0") if row is None else quota_quantity_decimal(row[0], name="used")
            state = TenantQuotaCounterState(
                tenant_id=tid,
                counter_key=key,
                window_key=window,
                used=current + delta,
                updated_at=updated_at,
            )
            conn.execute(
                """
                INSERT INTO tenant_quota_counters(
                    tenant_id, counter_key, window_key, used_text, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, counter_key, window_key)
                DO UPDATE SET used_text = excluded.used_text, updated_at = excluded.updated_at
                """,
                (tid, key, window, str(state.used), updated_at.isoformat()),
            )
        return state

    def delete(self, *, tenant_id: str, counter_key: str | None = None) -> None:
        tid = require_tenant_id(tenant_id)
        with self._connect() as conn:
            if counter_key is None:
                conn.execute("DELETE FROM tenant_quota_counters WHERE tenant_id = ?", (tid,))
            else:
                conn.execute(
                    "DELETE FROM tenant_quota_counters WHERE tenant_id = ? AND counter_key = ?",
                    (tid, str(counter_key).strip()),
                )

    def list_for_tenant(self, *, tenant_id: str) -> tuple[TenantQuotaCounterState, ...]:
        tid = require_tenant_id(tenant_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tenant_id, counter_key, window_key, used_text, updated_at "
                "FROM tenant_quota_counters WHERE tenant_id = ? "
                "ORDER BY counter_key ASC, window_key ASC",
                (tid,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def migrate_legacy_file(self, path: str | Path) -> int:
        legacy_path = Path(path)
        if not legacy_path.exists():
            return 0
        raw = read_json_or_default(legacy_path, default={"states": []})
        rows = raw.get("states", []) if isinstance(raw, dict) else []
        states = tuple(
            _normalized_state(
                TenantQuotaCounterState(
                    tenant_id=str(item.get("tenant_id") or ""),
                    counter_key=str(item.get("counter_key") or ""),
                    window_key=str(item.get("window_key") or ""),
                    used=quota_quantity_decimal(item.get("used", 0), name="used"),
                    updated_at=datetime.fromisoformat(str(item.get("updated_at") or "")),
                )
            )
            for item in (dict(row) for row in rows)
        )
        migration_key = "legacy_json_migration_v1"
        marker = str(legacy_path.resolve())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT value FROM tenant_quota_counter_meta WHERE key = ?",
                (migration_key,),
            ).fetchone()
            if existing is not None and str(existing[0]) == marker:
                return 0
            for state in states:
                conn.execute(
                    """
                    INSERT INTO tenant_quota_counters(
                        tenant_id, counter_key, window_key, used_text, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, counter_key, window_key)
                    DO UPDATE SET used_text = excluded.used_text, updated_at = excluded.updated_at
                    """,
                    (
                        state.tenant_id,
                        state.counter_key,
                        state.window_key,
                        str(state.used),
                        state.updated_at.isoformat(),
                    ),
                )
            conn.execute(
                "INSERT INTO tenant_quota_counter_meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (migration_key, marker),
            )
        return len(states)

def build_default_tenant_quota_counter_store() -> TenantQuotaCounterStore:
    mode = os.getenv("BUSINESAIOS_TENANT_QUOTA_COUNTER_STORE_BACKEND", "sqlite").strip().lower()
    if mode == "memory":
        return InMemoryTenantQuotaCounterStore()
    if mode == "file":
        return PersistentTenantQuotaCounterStore()
    if mode != "sqlite":
        raise ValueError(f"unsupported tenant quota counter backend: {mode}")
    store = SQLiteTenantQuotaCounterStore()
    store.migrate_legacy_file(tenant_quota_counter_store_path())
    return store

