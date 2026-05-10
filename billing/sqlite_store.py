from __future__ import annotations

from runtime.platform.billing_sqlite_store import (
    CANON_PLATFORM_BILLING_SQLITE_STORE,
    PlatformSqliteCollectionResultStore,
    PlatformSqliteLedgerStore,
)

CANON_BILLING_SQLITE_STORE = True


class SqliteCollectionResultStore(PlatformSqliteCollectionResultStore):
    """Billing-facing collection result store facade.

    SQLite ownership lives in runtime.platform.billing_sqlite_store.
    """


class SqliteLedgerStore(PlatformSqliteLedgerStore):
    """Billing-facing ledger store facade.

    SQLite ownership lives in runtime.platform.billing_sqlite_store.
    """


__all__ = [
    'CANON_BILLING_SQLITE_STORE',
    'CANON_PLATFORM_BILLING_SQLITE_STORE',
    'SqliteCollectionResultStore',
    'SqliteLedgerStore',
]
