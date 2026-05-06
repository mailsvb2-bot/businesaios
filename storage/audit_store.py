from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any, Mapping
import json
import uuid

from governance.persistence_codec import to_jsonable
from storage.migration_registry import MigrationRegistry, default_storage_migration_registry
from storage.postgres_session import PostgresSessionFactory
from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


CANON_STORAGE_AUDIT_STORE = True


def utc_now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class AuditRecord:
    tenant_id: str
    scope: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    retention_until: datetime | None = None
    legal_hold: bool = False
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        for field_name in ("scope", "actor", "action", "entity_type", "entity_id", "event_id"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.retention_until is not None and self.retention_until.tzinfo is None:
            raise ValueError("retention_until must be timezone-aware")
        if self.retention_until is not None and self.retention_until < self.created_at:
            raise ValueError("retention_until must be >= created_at")

    def normalized(self) -> "AuditRecord":
        record = AuditRecord(
            tenant_id=normalize_storage_tenant_id(self.tenant_id),
            scope=str(self.scope).strip(),
            actor=str(self.actor).strip(),
            action=str(self.action).strip(),
            entity_type=str(self.entity_type).strip(),
            entity_id=str(self.entity_id).strip(),
            payload=to_jsonable(dict(self.payload)),
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            created_at=self.created_at,
            retention_until=self.retention_until,
            legal_hold=bool(self.legal_hold),
            event_id=str(self.event_id).strip(),
        )
        record.validate()
        return record

    @property
    def partition_key(self) -> str:
        return build_partition_key(self.tenant_id, scope=f"audit_{self.scope}")

    @property
    def payload_sha256(self) -> str:
        normalized = self.normalized()
        return sha256(_json_dumps(normalized.payload).encode("utf-8")).hexdigest()

    def to_row(self) -> dict[str, object]:
        record = self.normalized()
        return {
            "event_id": record.event_id,
            "tenant_id": record.tenant_id,
            "partition_key": record.partition_key,
            "scope": record.scope,
            "actor": record.actor,
            "action": record.action,
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
            "created_at": record.created_at.isoformat(),
            "payload_json": _json_dumps(record.payload),
            "payload_sha256": record.payload_sha256,
            "labels_json": _json_dumps(record.labels),
            "retention_until": None if record.retention_until is None else record.retention_until.isoformat(),
            "legal_hold": 1 if record.legal_hold else 0,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "AuditRecord":
        retention_until_raw = row.get("retention_until")
        return cls(
            event_id=str(row.get("event_id") or ""),
            tenant_id=str(row.get("tenant_id") or "global"),
            scope=str(row.get("scope") or ""),
            actor=str(row.get("actor") or ""),
            action=str(row.get("action") or ""),
            entity_type=str(row.get("entity_type") or ""),
            entity_id=str(row.get("entity_id") or ""),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
            payload=json.loads(str(row.get("payload_json") or "{}")),
            labels=json.loads(str(row.get("labels_json") or "{}")),
            retention_until=None if retention_until_raw in (None, "") else datetime.fromisoformat(str(retention_until_raw)),
            legal_hold=bool(row.get("legal_hold") or 0),
        ).normalized()


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._items: dict[str, AuditRecord] = {}
        self._lock = RLock()

    def append(self, record: AuditRecord) -> AuditRecord:
        normalized = record.normalized()
        with self._lock:
            self._items[normalized.event_id] = normalized
        return normalized

    def get(self, event_id: str) -> AuditRecord | None:
        with self._lock:
            return self._items.get(str(event_id).strip())

    def list_for_tenant(self, *, tenant_id: str, scope: str | None = None, limit: int = 100) -> tuple[AuditRecord, ...]:
        normalized_tenant = normalize_storage_tenant_id(tenant_id)
        normalized_scope = None if scope is None else str(scope).strip()
        with self._lock:
            items = [
                item
                for item in self._items.values()
                if item.tenant_id == normalized_tenant and (normalized_scope is None or item.scope == normalized_scope)
            ]
        items.sort(key=lambda item: (item.created_at, item.event_id), reverse=True)
        return tuple(items[: max(1, int(limit))])

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = now or utc_now()
        with self._lock:
            expired_ids = [
                event_id
                for event_id, item in self._items.items()
                if (not item.legal_hold) and item.retention_until is not None and item.retention_until <= moment
            ]
            for event_id in expired_ids:
                self._items.pop(event_id, None)
        return len(expired_ids)


class SqliteAuditStore:
    def __init__(self, session_factory: SqliteSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        self._session_factory = session_factory
        self._migrations = migrations or default_storage_migration_registry()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def append(self, record: AuditRecord) -> AuditRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT OR REPLACE INTO storage_audit_log(
                    event_id, tenant_id, partition_key, scope, actor, action, entity_type, entity_id,
                    created_at, payload_json, payload_sha256, labels_json, retention_until, legal_hold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["event_id"], row["tenant_id"], row["partition_key"], row["scope"], row["actor"], row["action"],
                    row["entity_type"], row["entity_id"], row["created_at"], row["payload_json"], row["payload_sha256"],
                    row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
        return normalized

    def get(self, event_id: str) -> AuditRecord | None:
        with self._session_factory.open() as session:
            row = session.fetchone("SELECT * FROM storage_audit_log WHERE event_id = ?", (str(event_id).strip(),))
        return None if row is None else AuditRecord.from_row(dict(row))

    def list_for_tenant(self, *, tenant_id: str, scope: str | None = None, limit: int = 100) -> tuple[AuditRecord, ...]:
        tenant = normalize_storage_tenant_id(tenant_id)
        params: list[object] = [tenant]
        sql = "SELECT * FROM storage_audit_log WHERE tenant_id = ?"
        if scope is not None:
            sql += " AND scope = ?"
            params.append(str(scope).strip())
        sql += " ORDER BY created_at DESC, event_id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._session_factory.open() as session:
            rows = session.fetchall(sql, tuple(params))
        return tuple(AuditRecord.from_row(dict(row)) for row in rows)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = (now or utc_now()).isoformat()
        with self._session_factory.open() as session:
            cursor = session.execute(
                "DELETE FROM storage_audit_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= ?",
                (moment,),
            )
            return int(cursor.rowcount or 0)


class PostgresAuditStore:
    def __init__(self, session_factory: PostgresSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        self._session_factory = session_factory
        self._migrations = migrations or default_storage_migration_registry()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def append(self, record: AuditRecord) -> AuditRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT INTO storage_audit_log(
                    event_id, tenant_id, partition_key, scope, actor, action, entity_type, entity_id,
                    created_at, payload_json, payload_sha256, labels_json, retention_until, legal_hold
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    tenant_id=EXCLUDED.tenant_id,
                    partition_key=EXCLUDED.partition_key,
                    scope=EXCLUDED.scope,
                    actor=EXCLUDED.actor,
                    action=EXCLUDED.action,
                    entity_type=EXCLUDED.entity_type,
                    entity_id=EXCLUDED.entity_id,
                    created_at=EXCLUDED.created_at,
                    payload_json=EXCLUDED.payload_json,
                    payload_sha256=EXCLUDED.payload_sha256,
                    labels_json=EXCLUDED.labels_json,
                    retention_until=EXCLUDED.retention_until,
                    legal_hold=EXCLUDED.legal_hold
                """,
                (
                    row["event_id"], row["tenant_id"], row["partition_key"], row["scope"], row["actor"], row["action"],
                    row["entity_type"], row["entity_id"], row["created_at"], row["payload_json"], row["payload_sha256"],
                    row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
        return normalized

    def get(self, event_id: str) -> AuditRecord | None:
        with self._session_factory.open() as session:
            row = session.fetchone("SELECT * FROM storage_audit_log WHERE event_id = %s", (str(event_id).strip(),))
        return None if row is None else AuditRecord.from_row(row)

    def list_for_tenant(self, *, tenant_id: str, scope: str | None = None, limit: int = 100) -> tuple[AuditRecord, ...]:
        tenant = normalize_storage_tenant_id(tenant_id)
        params: list[object] = [tenant]
        sql = "SELECT * FROM storage_audit_log WHERE tenant_id = %s"
        if scope is not None:
            sql += " AND scope = %s"
            params.append(str(scope).strip())
        sql += " ORDER BY created_at DESC, event_id DESC LIMIT %s"
        params.append(max(1, int(limit)))
        with self._session_factory.open() as session:
            rows = session.fetchall(sql, tuple(params))
        return tuple(AuditRecord.from_row(row) for row in rows)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = (now or utc_now()).isoformat()
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT COUNT(*) AS deleted_count FROM storage_audit_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= %s",
                (moment,),
            )
            deleted_count = int((row or {}).get("deleted_count") or 0)
            session.execute(
                "DELETE FROM storage_audit_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= %s",
                (moment,),
            )
        return deleted_count


__all__ = [
    "CANON_STORAGE_AUDIT_STORE",
    "AuditRecord",
    "InMemoryAuditStore",
    "PostgresAuditStore",
    "SqliteAuditStore",
    "utc_now",
]
