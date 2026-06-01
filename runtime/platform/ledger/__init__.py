"""DecisionLedger implementations.

Contract: try_mark_executed(envelope) -> bool
  - Must be atomic INSERT with decision_id as PRIMARY KEY.
  - No read-then-insert patterns.

Backends:
  - SQLite (dev/tests)
  - Postgres (production)

Important runtime property:
  Do not import SQLite at package import time.
  SQLite imports are loaded lazily via __getattr__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "SqliteLedger",
    "PostgresLedger",
]


if TYPE_CHECKING:  # pragma: no cover
    from .postgres_ledger import PostgresLedger as PostgresLedger
    from .sqlite_ledger import SqliteLedger as SqliteLedger


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name == "SqliteLedger":
        from .sqlite_ledger import SqliteLedger

        return SqliteLedger
    if name == "PostgresLedger":
        from .postgres_ledger import PostgresLedger

        return PostgresLedger
    raise AttributeError(name)
