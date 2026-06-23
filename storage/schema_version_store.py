from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Mapping
import hashlib
import json
import re

from governance.persistence_codec import to_jsonable
from storage.migration_registry import MigrationRegistry, default_storage_migration_registry
from storage.postgres_session import PostgresSessionFactory
from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import normalize_storage_tenant_id


CANON_STORAGE_SCHEMA_VERSION_STORE = True
CANON_STORAGE_SCHEMA_VERSION_EXPLICIT_LEGACY_FACTORY = True


_VERSION_NUMBER_RE = re.compile(r"\d+")


def utc_now() -> datetime:
    return datetime.now(UTC)


def _coerce_version(value: object) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "0").strip()
    if text.isdigit():
        return int(text)
    match = _VERSION_NUMBER_RE.search(text)
    if match:
        return int(match.group(0))
    return 0


@dataclass(frozen=True)
class SchemaVersionRecord:
    scope: str
    component: str
    version: int
    tenant_id: str = "global"
    fingerprint: str = ""
    applied_at: datetime = field(default_factory=utc_now)
    applied_by: str = "system"
    details: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy(
        cls,
        *,
        component: str,
        version: int | str,
        checksum: str | None = None,
        scope: str = "storage",
        tenant_id: str = "global",
        fingerprint: str = "",
        applied_at: datetime | None = None,
        applied_by: str = "system",
        details: Mapping[str, Any] | None = None,
    ) -> "SchemaVersionRecord":
        return cls(
            scope=str(scope or "storage").strip() or "storage",
            component=str(component).strip(),
            version=_coerce_version(version),
            tenant_id=tenant_id,
            fingerprint=str(fingerprint or checksum or "").strip(),
            applied_at=applied_at or utc_now(),
            applied_by=applied_by,
            details=dict(details or {}),
        )

    def validate(self) -> None:
        if not str(self.scope or "").strip():
            raise ValueError("scope is required")
        if not str(self.component or "").strip():
            raise ValueError("component is required")
        if int(self.version) < 0:
            raise ValueError("version must be >= 0")
        if self.applied_at.tzinfo is None:
            raise ValueError("applied_at must be timezone-aware")

    @property
    def checksum(self) -> str:
        return self.fingerprint

    def normalized(self) -> "SchemaVersionRecord":
        serialized_details = to_jsonable(dict(self.details))
        fingerprint = self.fingerprint or hashlib.sha256(
            json.dumps(serialized_details, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        record = SchemaVersionRecord(
            scope=str(self.scope).strip(),
            component=str(self.component).strip(),
            version=int(self.version),
            tenant_id=normalize_storage_tenant_id(self.tenant_id),
            fingerprint=str(fingerprint).strip(),
            applied_at=self.applied_at,
            applied_by=str(self.applied_by or "system").strip() or "system",
            details=serialized_details,
        )
        record.validate()
        return record

    def to_row(self) -> dict[str, object]:
        record = self.normalized()
        return {
            "scope": record.scope,
            "tenant_id": record.tenant_id,
            "component": record.component,
            "version": record.version,
            "fingerprint": record.fingerprint,
            "applied_at": record.applied_at.isoformat(),
            "applied_by": record.applied_by,
            "details_json": json.dumps(record.details, ensure_ascii=False, sort_keys=True),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "SchemaVersionRecord":
        details_json = str(row.get("details_json") or "{}")
        return cls(
            scope=str(row.get("scope") or ""),
            tenant_id=str(row.get("tenant_id") or "global"),
            component=str(row.get("component") or ""),
            version=int(row.get("version") or 0),
            fingerprint=str(row.get("fingerprint") or ""),
            applied_at=datetime.fromisoformat(str(row.get("applied_at"))),
            applied_by=str(row.get("applied_by") or "system"),
            details=json.loads(details_json),
        ).normalized()


class InMemorySchemaVersionStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], SchemaVersionRecord] = {}
        self._lock = RLock()

    def upsert(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        normalized = record.normalized()
        with self._lock:
            self._items[(normalized.scope, normalized.tenant_id, normalized.component)] = normalized
        return normalized

    def set(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        return self.upsert(record)

    def get(self, component: str | None = None, *, scope: str = "storage", tenant_id: str = "global") -> SchemaVersionRecord | None:
        if component is None:
            raise TypeError("component is required")
        key = (str(scope).strip(), normalize_storage_tenant_id(tenant_id), str(component).strip())
        with self._lock:
            return self._items.get(key)

    def list_all(self) -> tuple[SchemaVersionRecord, ...]:
        with self._lock:
            return tuple(sorted(self._items.values(), key=lambda item: (item.scope, item.tenant_id, item.component)))

    def current_version(self, *, scope: str, component: str, tenant_id: str = "global") -> int:
        record = self.get(component=component, scope=scope, tenant_id=tenant_id)
        return 0 if record is None else int(record.version)


class _PersistentSchemaVersionStore:
    def __init__(self, *, migrations: MigrationRegistry | None = None) -> None:
        self._migrations = migrations or default_storage_migration_registry()

    def _normalize_record(self, record: SchemaVersionRecord) -> tuple[SchemaVersionRecord, dict[str, object]]:
        normalized = record.normalized()
        return normalized, normalized.to_row()


class SqliteSchemaVersionStore(_PersistentSchemaVersionStore):
    def __init__(self, session_factory: SqliteSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        super().__init__(migrations=migrations)
        self._session_factory = session_factory
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def upsert(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        normalized, row = self._normalize_record(record)
        with self._session_factory.open() as session:
            session.execute(
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
                (
                    row["scope"],
                    row["tenant_id"],
                    row["component"],
                    row["version"],
                    row["fingerprint"],
                    row["applied_at"],
                    row["applied_by"],
                    row["details_json"],
                ),
            )
        return normalized

    def set(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        return self.upsert(record)

    def get(self, component: str | None = None, *, scope: str = "storage", tenant_id: str = "global") -> SchemaVersionRecord | None:
        if component is None:
            raise TypeError("component is required")
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT * FROM storage_schema_versions WHERE scope = ? AND tenant_id = ? AND component = ?",
                (str(scope).strip(), normalize_storage_tenant_id(tenant_id), str(component).strip()),
            )
        return None if row is None else SchemaVersionRecord.from_row(dict(row))

    def list_all(self) -> tuple[SchemaVersionRecord, ...]:
        with self._session_factory.open() as session:
            rows = session.fetchall("SELECT * FROM storage_schema_versions ORDER BY scope, tenant_id, component", ())
        return tuple(SchemaVersionRecord.from_row(dict(row)) for row in rows)

    def current_version(self, *, scope: str, component: str, tenant_id: str = "global") -> int:
        record = self.get(component=component, scope=scope, tenant_id=tenant_id)
        return 0 if record is None else int(record.version)


class PostgresSchemaVersionStore(_PersistentSchemaVersionStore):
    def __init__(self, session_factory: PostgresSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        super().__init__(migrations=migrations)
        self._session_factory = session_factory
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def upsert(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        normalized, row = self._normalize_record(record)
        with self._session_factory.open() as session:
            session.execute(
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
                (
                    row["scope"],
                    row["tenant_id"],
                    row["component"],
                    row["version"],
                    row["fingerprint"],
                    row["applied_at"],
                    row["applied_by"],
                    row["details_json"],
                ),
            )
        return normalized

    def set(self, record: SchemaVersionRecord) -> SchemaVersionRecord:
        return self.upsert(record)

    def get(self, component: str | None = None, *, scope: str = "storage", tenant_id: str = "global") -> SchemaVersionRecord | None:
        if component is None:
            raise TypeError("component is required")
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT * FROM storage_schema_versions WHERE scope = %s AND tenant_id = %s AND component = %s",
                (str(scope).strip(), normalize_storage_tenant_id(tenant_id), str(component).strip()),
            )
        return None if row is None else SchemaVersionRecord.from_row(row)

    def list_all(self) -> tuple[SchemaVersionRecord, ...]:
        with self._session_factory.open() as session:
            rows = session.fetchall("SELECT * FROM storage_schema_versions ORDER BY scope, tenant_id, component", ())
        return tuple(SchemaVersionRecord.from_row(row) for row in rows)

    def current_version(self, *, scope: str, component: str, tenant_id: str = "global") -> int:
        record = self.get(component=component, scope=scope, tenant_id=tenant_id)
        return 0 if record is None else int(record.version)


__all__ = [
    "CANON_STORAGE_SCHEMA_VERSION_STORE",
    "CANON_STORAGE_SCHEMA_VERSION_EXPLICIT_LEGACY_FACTORY",
    "SchemaVersionRecord",
    "InMemorySchemaVersionStore",
    "SqliteSchemaVersionStore",
    "PostgresSchemaVersionStore",
]
