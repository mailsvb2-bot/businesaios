"""Event store package.

Important runtime property:
  Do not import SQLite implementations at package import time.

This repo supports multiple backends:
  - Memory (tests/examples)
  - SQLite (dev/tests)
  - Postgres (production)

To avoid accidentally pulling SQLite into production processes,
implementations are loaded lazily via __getattr__.
Historical split modules now alias directly to the canonical owner modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contracts.event_store import (
    EventStore,
    EventStoreReader,
    EventStoreWriter,
    iter_events_strict,
    supports_event_store,
)
from runtime.lazy_namespace import install_module_aliases

CANON_EVENT_STORE_NAMESPACE = True

__all__ = [
    "EventStore",
    "EventStoreReader",
    "EventStoreWriter",
    "supports_event_store",
    "iter_events_strict",
    "MemoryEventStore",
    "SqliteEventStore",
    "PostgresEventStore",
]

_COMPAT_ALIAS_MAP = {
    "contract": "contracts.event_store",
    "postgres_event_store_part1": "runtime.platform.event_store.postgres_event_store",
    "postgres_event_store_part2": "runtime.platform.event_store.postgres_event_store",
    "sqlite_read_queries_part1": "runtime.platform.event_store.sqlite_read_queries",
    "sqlite_read_queries_part2": "runtime.platform.event_store.sqlite_read_queries",
    "_sqlite_user_state": "runtime.platform.event_store.sqlite_user_state",
}

if TYPE_CHECKING:  # pragma: no cover
    from .memory_event_store import MemoryEventStore as MemoryEventStore
    from .postgres_event_store import PostgresEventStore as PostgresEventStore
    from .sqlite_event_store import SqliteEventStore as SqliteEventStore

install_module_aliases(__name__, _COMPAT_ALIAS_MAP)


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name == "MemoryEventStore":
        from .memory_event_store import MemoryEventStore
        return MemoryEventStore
    if name == "SqliteEventStore":
        from .sqlite_event_store import SqliteEventStore
        return SqliteEventStore
    if name == "PostgresEventStore":
        from .postgres_event_store import PostgresEventStore
        return PostgresEventStore
    raise AttributeError(name)

