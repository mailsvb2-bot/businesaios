from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.platform.client_outcome_sqlite_core import (
    CANON_CLIENT_OUTCOME_SINGLE_REPLICA_FAIL_CLOSED,
    CANON_CLIENT_OUTCOME_SQLITE_PERSISTENCE,
    SQLiteJsonRegistryBackend,
    _SQLiteOwner,
    client_outcome_db_path,
    enforce_client_outcome_replica_contract,
)
from runtime.platform.client_outcome_sqlite_ledger import SQLiteClientOutcomeLedgerStore
from runtime.platform.client_outcome_sqlite_metrics import SQLiteTenantMetricsRegistry


@dataclass(frozen=True)
class ClientOutcomePersistenceOwner:
    _owner: _SQLiteOwner

    @classmethod
    def default(cls) -> 'ClientOutcomePersistenceOwner':
        return cls(_owner=_SQLiteOwner())

    @property
    def path(self) -> Path:
        return self._owner.path

    def registry(self, namespace: str) -> SQLiteJsonRegistryBackend:
        return SQLiteJsonRegistryBackend(namespace=namespace, owner=self._owner)

    def ledger_store(self) -> SQLiteClientOutcomeLedgerStore:
        return SQLiteClientOutcomeLedgerStore(owner=self._owner)

    def metrics_registry(self) -> SQLiteTenantMetricsRegistry:
        return SQLiteTenantMetricsRegistry(owner=self._owner)


__all__ = [
    'CANON_CLIENT_OUTCOME_SINGLE_REPLICA_FAIL_CLOSED',
    'CANON_CLIENT_OUTCOME_SQLITE_PERSISTENCE',
    'ClientOutcomePersistenceOwner',
    'SQLiteClientOutcomeLedgerStore',
    'SQLiteJsonRegistryBackend',
    'SQLiteTenantMetricsRegistry',
    'client_outcome_db_path',
    'enforce_client_outcome_replica_contract',
]
