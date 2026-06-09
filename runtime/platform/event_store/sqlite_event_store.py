from __future__ import annotations

"""Canonical sqlite event store implementation.

Public API is unchanged; callers must keep importing
``runtime.platform.event_store.sqlite_event_store``.
"""

import logging
import sqlite3

from runtime.platform.event_store.sqlite_event_store_query_api import SqliteEventStoreQueryApi
from runtime.platform.event_store.sqlite_event_store_retention_api import SqliteEventStoreRetentionApi
from runtime.platform.event_store.sqlite_event_store_settings_api import SqliteEventStoreSettingsApi
from runtime.platform.event_store.sqlite_event_store_write_api import SqliteEventStoreWriteApi
from runtime.platform.event_store.sqlite_schema import backfill_legacy_tenant_ids, init_schema
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

logger = logging.getLogger(__name__)


class SqliteEventStore(
    SqliteEventStoreWriteApi,
    SqliteEventStoreSettingsApi,
    SqliteEventStoreQueryApi,
    SqliteEventStoreRetentionApi,
):
    """Durable event store for dev/single-node."""

    def __init__(self, path: str):
        self._path = str(path)
        self._db: sqlite3.Connection | None = None

    def __enter__(self):
        self._db = sqlite3.connect(self._path, timeout=5.0, check_same_thread=False)
        configure_sqlite(self._db, prod=is_prod_env())
        self._db.execute("PRAGMA journal_mode=WAL;")
        init_schema(self._db)
        backfill_legacy_tenant_ids(self._db)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._db:
            self._db.close()
            self._db = None

    def ping(self) -> bool:
        try:
            assert self._db is not None
            self._db.execute("SELECT 1")
            return True
        except Exception:
            return False

    def commit(self) -> None:
        assert self._db is not None
        self._db.commit()

__all__ = ["SqliteEventStore"]
