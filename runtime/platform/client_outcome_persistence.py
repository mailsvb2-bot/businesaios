from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.platform.client_outcome_postgres_registry import PostgresJsonRegistryBackend
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
from runtime.platform.config.env_flags import env_str


@dataclass(frozen=True)
class ClientOutcomePersistenceOwner:
    _owner: _SQLiteOwner
    _postgres_dsn: str = ''

    @classmethod
    def default(cls) -> 'ClientOutcomePersistenceOwner':
        backend = env_str('BUSINESAIOS_CLIENT_OUTCOME_BACKEND', 'sqlite').strip().lower()
        if backend == 'postgres':
            dsn = env_str('POSTGRES_DSN', '').strip()
            if not dsn:
                raise RuntimeError('BUSINESAIOS_CLIENT_OUTCOME_BACKEND=postgres requires POSTGRES_DSN')
            return cls(_owner=_SQLiteOwner(), _postgres_dsn=dsn)
        if backend != 'sqlite':
            raise RuntimeError(f'unsupported client-outcome backend: {backend!r}')
        return cls(_owner=_SQLiteOwner())

    @property
    def path(self) -> Path:
        return self._owner.path

    def registry(self, namespace: str) -> SQLiteJsonRegistryBackend | PostgresJsonRegistryBackend:
        if self._postgres_dsn:
            return PostgresJsonRegistryBackend(namespace=namespace, dsn=self._postgres_dsn)
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
