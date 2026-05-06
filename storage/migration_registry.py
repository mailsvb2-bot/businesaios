from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Protocol, Sequence
import json


CANON_STORAGE_MIGRATION_REGISTRY = True


class SqlExecutor(Protocol):
    dialect: str

    def execute(self, sql: str, params: Sequence[object] | None = None) -> object: ...
    def fetchone(self, sql: str, params: Sequence[object] | None = None) -> object: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...] = field(default_factory=tuple)
    python_hook: Callable[[SqlExecutor], None] | None = None

    def validate(self) -> None:
        if int(self.version) < 1:
            raise ValueError("migration version must be >= 1")
        if not str(self.name or "").strip():
            raise ValueError("migration name is required")
        if not self.statements and self.python_hook is None:
            raise ValueError("migration must define SQL statements or python_hook")

    def apply(self, executor: SqlExecutor) -> None:
        self.validate()
        for statement in self.statements:
            sql = str(statement or "").strip()
            if sql:
                executor.execute(sql)
        if self.python_hook is not None:
            self.python_hook(executor)


class MigrationRegistry:
    def __init__(self, migrations: Sequence[Migration] | None = None) -> None:
        self._migrations: dict[int, Migration] = {}
        for migration in migrations or ():
            self.register(migration)

    def register(self, migration: Migration) -> None:
        migration.validate()
        version = int(migration.version)
        existing = self._migrations.get(version)
        if existing is not None and existing != migration:
            raise ValueError(f"duplicate migration version: {version}")
        self._migrations[version] = migration

    def versions(self) -> tuple[int, ...]:
        return tuple(sorted(self._migrations.keys()))

    def latest_version(self) -> int:
        versions = self.versions()
        return versions[-1] if versions else 0

    def _ensure_metadata_table(self, executor: SqlExecutor) -> None:
        executor.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_schema_versions (
                scope TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                component TEXT NOT NULL,
                version INTEGER NOT NULL,
                fingerprint TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                applied_by TEXT NOT NULL,
                details_json TEXT NOT NULL,
                PRIMARY KEY (scope, tenant_id, component)
            );
            """
        )

    def current_version(self, executor: SqlExecutor, *, scope: str = "storage", component: str = "storage_migrations") -> int:
        self._ensure_metadata_table(executor)
        if executor.dialect == "postgres":
            row = executor.fetchone(
                "SELECT version FROM storage_schema_versions WHERE scope = %s AND tenant_id = %s AND component = %s",
                (scope, "global", component),
            )
        else:
            row = executor.fetchone(
                "SELECT version FROM storage_schema_versions WHERE scope = ? AND tenant_id = ? AND component = ?",
                (scope, "global", component),
            )
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(row.get("version") or 0)
        return int(row[0])

    def pending(self, current_version: int) -> tuple[Migration, ...]:
        return tuple(self._migrations[version] for version in self.versions() if version > int(current_version))

    def _record_applied_migration(
        self,
        executor: SqlExecutor,
        *,
        migration: Migration,
        scope: str,
        component: str,
        applied_by: str,
    ) -> None:
        details_json = json.dumps({"migration_name": migration.name}, ensure_ascii=False, sort_keys=True)
        if executor.dialect == "postgres":
            executor.execute(
                """
                INSERT INTO storage_schema_versions(scope, tenant_id, component, version, fingerprint, applied_at, applied_by, details_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scope, tenant_id, component) DO UPDATE SET
                    version=EXCLUDED.version,
                    fingerprint=EXCLUDED.fingerprint,
                    applied_at=EXCLUDED.applied_at,
                    applied_by=EXCLUDED.applied_by,
                    details_json=EXCLUDED.details_json
                """,
                (scope, "global", component, migration.version, migration.name, _utc_now_iso(), applied_by, details_json),
            )
        else:
            executor.execute(
                """
                INSERT INTO storage_schema_versions(scope, tenant_id, component, version, fingerprint, applied_at, applied_by, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, tenant_id, component) DO UPDATE SET
                    version=excluded.version,
                    fingerprint=excluded.fingerprint,
                    applied_at=excluded.applied_at,
                    applied_by=excluded.applied_by,
                    details_json=excluded.details_json
                """,
                (scope, "global", component, migration.version, migration.name, _utc_now_iso(), applied_by, details_json),
            )

    def apply_pending(
        self,
        executor: SqlExecutor,
        *,
        scope: str = "storage",
        component: str = "storage_migrations",
        applied_by: str = "system",
    ) -> tuple[Migration, ...]:
        self._ensure_metadata_table(executor)
        current_version = self.current_version(executor, scope=scope, component=component)
        applied: list[Migration] = []
        try:
            for migration in self.pending(current_version):
                migration.apply(executor)
                self._record_applied_migration(
                    executor,
                    migration=migration,
                    scope=scope,
                    component=component,
                    applied_by=applied_by,
                )
                executor.commit()
                applied.append(migration)
        except Exception:
            executor.rollback()
            raise
        return tuple(applied)


_DEF = MigrationRegistry(
    [
        Migration(
            version=1,
            name="storage_core_tables",
            statements=(
                """
                CREATE TABLE IF NOT EXISTS storage_audit_log (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    partition_key TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    retention_until TEXT,
                    legal_hold INTEGER NOT NULL DEFAULT 0
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS storage_evidence_log (
                    evidence_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    partition_key TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    action_id TEXT,
                    action_type TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    refs_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    retention_until TEXT,
                    legal_hold INTEGER NOT NULL DEFAULT 0
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_storage_audit_tenant_created ON storage_audit_log(tenant_id, created_at);",
                "CREATE INDEX IF NOT EXISTS idx_storage_audit_partition_created ON storage_audit_log(partition_key, created_at);",
                "CREATE INDEX IF NOT EXISTS idx_storage_evidence_tenant_created ON storage_evidence_log(tenant_id, created_at);",
                "CREATE INDEX IF NOT EXISTS idx_storage_evidence_partition_created ON storage_evidence_log(partition_key, created_at);",
                "CREATE INDEX IF NOT EXISTS idx_storage_evidence_run ON storage_evidence_log(tenant_id, run_id);",
            ),
        )
    ]
)


def default_storage_migration_registry() -> MigrationRegistry:
    return MigrationRegistry([_DEF._migrations[version] for version in _DEF.versions()])


__all__ = [
    "CANON_STORAGE_MIGRATION_REGISTRY",
    "Migration",
    "MigrationRegistry",
    "SqlExecutor",
    "default_storage_migration_registry",
]
