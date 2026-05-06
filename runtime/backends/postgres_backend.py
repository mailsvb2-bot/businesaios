from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from storage.postgres_session import PostgresSessionFactory

CANON_PRODUCTION_POSTGRES_BACKEND = True


@dataclass(frozen=True)
class ProductionPostgresBackendConfig:
    dsn: str
    application_name: str = 'businesaios-postgres-backend'
    statement_timeout_ms: int = 30000
    lock_timeout_ms: int = 5000
    min_pool_size: int = 1
    max_pool_size: int = 10
    require_ssl: bool = True

    def validate(self) -> None:
        if not str(self.dsn or '').strip():
            raise ValueError('dsn is required')
        if self.min_pool_size < 1:
            raise ValueError('min_pool_size must be >= 1')
        if self.max_pool_size < self.min_pool_size:
            raise ValueError('max_pool_size must be >= min_pool_size')


@dataclass(frozen=True)
class ProductionPostgresBackend:
    config: ProductionPostgresBackendConfig
    session_factory: PostgresSessionFactory = field(init=False)

    def __post_init__(self) -> None:
        self.config.validate()
        object.__setattr__(self, 'session_factory', PostgresSessionFactory(
            dsn=self.config.dsn,
            application_name=self.config.application_name,
            statement_timeout_ms=self.config.statement_timeout_ms,
            lock_timeout_ms=self.config.lock_timeout_ms,
        ))

    def describe(self) -> dict[str, Any]:
        return {
            'backend': 'postgres',
            'application_name': self.config.application_name,
            'statement_timeout_ms': self.config.statement_timeout_ms,
            'lock_timeout_ms': self.config.lock_timeout_ms,
            'pool': {'min': self.config.min_pool_size, 'max': self.config.max_pool_size},
            'require_ssl': bool(self.config.require_ssl),
        }

    def healthcheck(self, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {'status': 'ready_for_credentials', 'backend': 'postgres', 'details': self.describe()}
        with self.session_factory.open() as session:
            row = session.fetchone('SELECT 1 AS ok;')
            return {'status': 'ok' if row and int(row['ok']) == 1 else 'degraded', 'backend': 'postgres', 'details': self.describe()}

    def execute(self, *, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None) -> None:
        with self.session_factory.open() as session:
            session.execute(sql, params)
            session.commit()

    def fetchall(self, *, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with self.session_factory.open() as session:
            return session.fetchall(sql, params)
