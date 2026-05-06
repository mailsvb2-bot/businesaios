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


CANON_STORAGE_EVIDENCE_STORE = True


def utc_now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class EvidenceRecord:
    tenant_id: str
    scope: str
    run_id: str
    action_type: str
    verification_status: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    refs: tuple[str, ...] = field(default_factory=tuple)
    labels: Mapping[str, str] = field(default_factory=dict)
    action_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    retention_until: datetime | None = None
    legal_hold: bool = False
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        for field_name in ("scope", "run_id", "action_type", "verification_status", "evidence_id"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.retention_until is not None and self.retention_until.tzinfo is None:
            raise ValueError("retention_until must be timezone-aware")
        if self.retention_until is not None and self.retention_until < self.created_at:
            raise ValueError("retention_until must be >= created_at")

    def normalized(self) -> "EvidenceRecord":
        record = EvidenceRecord(
            tenant_id=normalize_storage_tenant_id(self.tenant_id),
            scope=str(self.scope).strip(),
            run_id=str(self.run_id).strip(),
            action_type=str(self.action_type).strip(),
            verification_status=str(self.verification_status).strip(),
            payload=to_jsonable(dict(self.payload)),
            refs=tuple(str(item).strip() for item in self.refs if str(item).strip()),
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            action_id=None if self.action_id is None else str(self.action_id).strip(),
            created_at=self.created_at,
            retention_until=self.retention_until,
            legal_hold=bool(self.legal_hold),
            evidence_id=str(self.evidence_id).strip(),
        )
        record.validate()
        return record

    @property
    def partition_key(self) -> str:
        return build_partition_key(self.tenant_id, scope=f"evidence_{self.scope}")

    @property
    def payload_sha256(self) -> str:
        normalized = self.normalized()
        return sha256(_json_dumps(normalized.payload).encode("utf-8")).hexdigest()

    def to_row(self) -> dict[str, object]:
        record = self.normalized()
        return {
            "evidence_id": record.evidence_id,
            "tenant_id": record.tenant_id,
            "partition_key": record.partition_key,
            "scope": record.scope,
            "run_id": record.run_id,
            "action_id": record.action_id,
            "action_type": record.action_type,
            "verification_status": record.verification_status,
            "created_at": record.created_at.isoformat(),
            "refs_json": _json_dumps(record.refs),
            "payload_json": _json_dumps(record.payload),
            "payload_sha256": record.payload_sha256,
            "labels_json": _json_dumps(record.labels),
            "retention_until": None if record.retention_until is None else record.retention_until.isoformat(),
            "legal_hold": 1 if record.legal_hold else 0,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "EvidenceRecord":
        retention_until_raw = row.get("retention_until")
        return cls(
            evidence_id=str(row.get("evidence_id") or ""),
            tenant_id=str(row.get("tenant_id") or "global"),
            scope=str(row.get("scope") or ""),
            run_id=str(row.get("run_id") or ""),
            action_id=None if row.get("action_id") in (None, "") else str(row.get("action_id")),
            action_type=str(row.get("action_type") or ""),
            verification_status=str(row.get("verification_status") or ""),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
            refs=tuple(json.loads(str(row.get("refs_json") or "[]"))),
            payload=json.loads(str(row.get("payload_json") or "{}")),
            labels=json.loads(str(row.get("labels_json") or "{}")),
            retention_until=None if retention_until_raw in (None, "") else datetime.fromisoformat(str(retention_until_raw)),
            legal_hold=bool(row.get("legal_hold") or 0),
        ).normalized()


class InMemoryEvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, EvidenceRecord] = {}
        self._lock = RLock()

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        with self._lock:
            self._items[normalized.evidence_id] = normalized
        return normalized

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._lock:
            return self._items.get(str(evidence_id).strip())

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        normalized_tenant = normalize_storage_tenant_id(tenant_id)
        normalized_run_id = None if run_id is None else str(run_id).strip()
        with self._lock:
            items = [
                item
                for item in self._items.values()
                if item.tenant_id == normalized_tenant and (normalized_run_id is None or item.run_id == normalized_run_id)
            ]
        items.sort(key=lambda item: (item.created_at, item.evidence_id), reverse=True)
        return tuple(items[: max(1, int(limit))])

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = now or utc_now()
        with self._lock:
            expired_ids = [
                evidence_id
                for evidence_id, item in self._items.items()
                if (not item.legal_hold) and item.retention_until is not None and item.retention_until <= moment
            ]
            for evidence_id in expired_ids:
                self._items.pop(evidence_id, None)
        return len(expired_ids)


class SqliteEvidenceStore:
    def __init__(self, session_factory: SqliteSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        self._session_factory = session_factory
        self._migrations = migrations or default_storage_migration_registry()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT OR REPLACE INTO storage_evidence_log(
                    evidence_id, tenant_id, partition_key, scope, run_id, action_id, action_type,
                    verification_status, created_at, refs_json, payload_json, payload_sha256,
                    labels_json, retention_until, legal_hold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["evidence_id"], row["tenant_id"], row["partition_key"], row["scope"], row["run_id"], row["action_id"],
                    row["action_type"], row["verification_status"], row["created_at"], row["refs_json"], row["payload_json"],
                    row["payload_sha256"], row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
        return normalized

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._session_factory.open() as session:
            row = session.fetchone("SELECT * FROM storage_evidence_log WHERE evidence_id = ?", (str(evidence_id).strip(),))
        return None if row is None else EvidenceRecord.from_row(dict(row))

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        tenant = normalize_storage_tenant_id(tenant_id)
        params: list[object] = [tenant]
        sql = "SELECT * FROM storage_evidence_log WHERE tenant_id = ?"
        if run_id is not None:
            sql += " AND run_id = ?"
            params.append(str(run_id).strip())
        sql += " ORDER BY created_at DESC, evidence_id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._session_factory.open() as session:
            rows = session.fetchall(sql, tuple(params))
        return tuple(EvidenceRecord.from_row(dict(row)) for row in rows)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = (now or utc_now()).isoformat()
        with self._session_factory.open() as session:
            cursor = session.execute(
                "DELETE FROM storage_evidence_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= ?",
                (moment,),
            )
            return int(cursor.rowcount or 0)


class PostgresEvidenceStore:
    def __init__(self, session_factory: PostgresSessionFactory, *, migrations: MigrationRegistry | None = None) -> None:
        self._session_factory = session_factory
        self._migrations = migrations or default_storage_migration_registry()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._session_factory.open() as session:
            self._migrations.apply_pending(session)

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT INTO storage_evidence_log(
                    evidence_id, tenant_id, partition_key, scope, run_id, action_id, action_type,
                    verification_status, created_at, refs_json, payload_json, payload_sha256,
                    labels_json, retention_until, legal_hold
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (evidence_id) DO UPDATE SET
                    tenant_id=EXCLUDED.tenant_id,
                    partition_key=EXCLUDED.partition_key,
                    scope=EXCLUDED.scope,
                    run_id=EXCLUDED.run_id,
                    action_id=EXCLUDED.action_id,
                    action_type=EXCLUDED.action_type,
                    verification_status=EXCLUDED.verification_status,
                    created_at=EXCLUDED.created_at,
                    refs_json=EXCLUDED.refs_json,
                    payload_json=EXCLUDED.payload_json,
                    payload_sha256=EXCLUDED.payload_sha256,
                    labels_json=EXCLUDED.labels_json,
                    retention_until=EXCLUDED.retention_until,
                    legal_hold=EXCLUDED.legal_hold
                """,
                (
                    row["evidence_id"], row["tenant_id"], row["partition_key"], row["scope"], row["run_id"], row["action_id"],
                    row["action_type"], row["verification_status"], row["created_at"], row["refs_json"], row["payload_json"],
                    row["payload_sha256"], row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
        return normalized

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._session_factory.open() as session:
            row = session.fetchone("SELECT * FROM storage_evidence_log WHERE evidence_id = %s", (str(evidence_id).strip(),))
        return None if row is None else EvidenceRecord.from_row(row)

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        tenant = normalize_storage_tenant_id(tenant_id)
        params: list[object] = [tenant]
        sql = "SELECT * FROM storage_evidence_log WHERE tenant_id = %s"
        if run_id is not None:
            sql += " AND run_id = %s"
            params.append(str(run_id).strip())
        sql += " ORDER BY created_at DESC, evidence_id DESC LIMIT %s"
        params.append(max(1, int(limit)))
        with self._session_factory.open() as session:
            rows = session.fetchall(sql, tuple(params))
        return tuple(EvidenceRecord.from_row(row) for row in rows)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        moment = (now or utc_now()).isoformat()
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT COUNT(*) AS deleted_count FROM storage_evidence_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= %s",
                (moment,),
            )
            deleted_count = int((row or {}).get("deleted_count") or 0)
            session.execute(
                "DELETE FROM storage_evidence_log WHERE legal_hold = 0 AND retention_until IS NOT NULL AND retention_until <= %s",
                (moment,),
            )
        return deleted_count


__all__ = [
    "CANON_STORAGE_EVIDENCE_STORE",
    "EvidenceRecord",
    "InMemoryEvidenceStore",
    "PostgresEvidenceStore",
    "SqliteEvidenceStore",
    "utc_now",
]
