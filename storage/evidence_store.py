from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from governance.persistence_codec import to_jsonable
from storage.migration_registry import MigrationRegistry, default_storage_migration_registry
from storage.postgres_session import PostgresSessionFactory
from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id

CANON_STORAGE_EVIDENCE_STORE = True
CANON_STORAGE_EVIDENCE_RECORD_EXPLICIT_LEGACY_FACTORY = True
EVIDENCE_LINEAGE_STAGES = ("source", "normalization", "derived_fact", "decision", "action", "outcome")
EVIDENCE_SCHEMA_VERSION = 2


def utc_now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _first_non_empty(*values: object, default: str) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _require_evidence_tenant_id(tenant_id: str) -> str:
    raw = str(tenant_id or "").strip()
    if not raw:
        raise ValueError("tenant_id is required")
    return normalize_storage_tenant_id(raw)


def _normalize_lineage(value: Mapping[str, object] | None) -> dict[str, str]:
    raw = dict(value or {})
    unknown = tuple(sorted(set(raw) - set(EVIDENCE_LINEAGE_STAGES)))
    if unknown:
        raise ValueError(f"unsupported evidence lineage stages: {','.join(unknown)}")
    return {stage: str(raw[stage]).strip() for stage in EVIDENCE_LINEAGE_STAGES if str(raw.get(stage) or '').strip()}


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
    source: str = "unknown"
    source_type: str = "unknown"
    business_id: str = "unknown"
    observed_at: datetime | None = None
    confidence: float | None = None
    privacy_class: str = "internal"
    retention_policy: str = "default"
    lineage: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = EVIDENCE_SCHEMA_VERSION

    @classmethod
    def from_legacy(
        cls,
        *,
        tenant_id: str,
        subject: str | None = None,
        evidence_type: str | None = None,
        scope: str | None = None,
        run_id: str | None = None,
        action_type: str | None = None,
        verification_status: str | None = None,
        payload: Mapping[str, Any] | None = None,
        refs: tuple[str, ...] | list[str] | None = None,
        labels: Mapping[str, str] | None = None,
        action_id: str | None = None,
        created_at: datetime | None = None,
        retention_until: datetime | None = None,
        legal_hold: bool = False,
        evidence_id: str | None = None,
        source: str = "legacy",
        source_type: str = "legacy",
        business_id: str | None = None,
        observed_at: datetime | None = None,
        confidence: float | None = None,
        privacy_class: str = "internal",
        retention_policy: str = "legacy",
        lineage: Mapping[str, str] | None = None,
    ) -> EvidenceRecord:
        return cls(
            tenant_id=tenant_id,
            scope=_first_non_empty(scope, subject, default="general"),
            run_id=_first_non_empty(run_id, default="default"),
            action_type=_first_non_empty(action_type, evidence_type, default="evidence"),
            verification_status=_first_non_empty(verification_status, default="recorded"),
            payload=dict(payload or {}),
            refs=tuple(refs or ()),
            labels=dict(labels or {}),
            action_id=action_id,
            created_at=created_at or utc_now(),
            retention_until=retention_until,
            legal_hold=legal_hold,
            evidence_id=evidence_id or str(uuid.uuid4()),
            source=source,
            source_type=source_type,
            business_id=business_id or "unknown",
            observed_at=observed_at,
            confidence=confidence,
            privacy_class=privacy_class,
            retention_policy=retention_policy,
            lineage=dict(lineage or {}),
        )

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        for field_name in (
            "scope", "run_id", "action_type", "verification_status", "evidence_id",
            "source", "source_type", "business_id", "privacy_class", "retention_policy",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if int(self.schema_version) not in (1, EVIDENCE_SCHEMA_VERSION):
            raise ValueError("unsupported evidence schema_version")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        _normalize_lineage(self.lineage)
        if self.retention_until is not None and self.retention_until.tzinfo is None:
            raise ValueError("retention_until must be timezone-aware")
        if self.retention_until is not None and self.retention_until < self.created_at:
            raise ValueError("retention_until must be >= created_at")

    def normalized(self) -> EvidenceRecord:
        tenant_id = _require_evidence_tenant_id(self.tenant_id)
        record = EvidenceRecord(
            tenant_id=tenant_id,
            scope=str(self.scope).strip(),
            run_id=str(self.run_id).strip(),
            action_type=str(self.action_type).strip(),
            verification_status=str(self.verification_status).strip(),
            payload=to_jsonable(dict(self.payload)),
            refs=tuple(str(item).strip() for item in self.refs if str(item).strip()),
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            action_id=None if self.action_id is None else str(self.action_id).strip(),
            created_at=self.created_at.astimezone(UTC),
            retention_until=None if self.retention_until is None else self.retention_until.astimezone(UTC),
            legal_hold=bool(self.legal_hold),
            evidence_id=str(self.evidence_id).strip(),
            source=str(self.source).strip(),
            source_type=str(self.source_type).strip(),
            business_id=str(self.business_id).strip(),
            observed_at=None if self.observed_at is None else self.observed_at.astimezone(UTC),
            confidence=None if self.confidence is None else float(self.confidence),
            privacy_class=str(self.privacy_class).strip(),
            retention_policy=str(self.retention_policy).strip(),
            lineage=_normalize_lineage(self.lineage),
            schema_version=int(self.schema_version),
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

    @property
    def evidence_sha256(self) -> str:
        normalized = self.normalized()
        envelope = {
            "schema_version": normalized.schema_version,
            "evidence_id": normalized.evidence_id,
            "tenant_id": normalized.tenant_id,
            "partition_key": normalized.partition_key,
            "scope": normalized.scope,
            "run_id": normalized.run_id,
            "action_id": normalized.action_id,
            "action_type": normalized.action_type,
            "verification_status": normalized.verification_status,
            "created_at": normalized.created_at.isoformat(),
            "source": normalized.source,
            "source_type": normalized.source_type,
            "business_id": normalized.business_id,
            "observed_at": None if normalized.observed_at is None else normalized.observed_at.isoformat(),
            "confidence": normalized.confidence,
            "privacy_class": normalized.privacy_class,
            "retention_policy": normalized.retention_policy,
            "lineage": dict(normalized.lineage),
            "refs": normalized.refs,
            "labels": dict(normalized.labels),
            "payload": normalized.payload,
            "retention_until": None if normalized.retention_until is None else normalized.retention_until.isoformat(),
            "legal_hold": normalized.legal_hold,
        }
        return sha256(_json_dumps(envelope).encode("utf-8")).hexdigest()

    @property
    def hash(self) -> str:
        return self.evidence_sha256

    @property
    def lineage_path(self) -> tuple[tuple[str, str], ...]:
        normalized = self.normalized()
        return tuple((stage, normalized.lineage[stage]) for stage in EVIDENCE_LINEAGE_STAGES if stage in normalized.lineage)

    @property
    def lineage_complete(self) -> bool:
        normalized = self.normalized()
        return all(stage in normalized.lineage for stage in EVIDENCE_LINEAGE_STAGES)

    def to_row(self) -> dict[str, object]:
        record = self.normalized()
        return {
            "evidence_id": record.evidence_id,
            "evidence_schema_version": record.schema_version,
            "tenant_id": record.tenant_id,
            "partition_key": record.partition_key,
            "scope": record.scope,
            "run_id": record.run_id,
            "action_id": record.action_id,
            "action_type": record.action_type,
            "verification_status": record.verification_status,
            "created_at": record.created_at.isoformat(),
            "source": record.source,
            "source_type": record.source_type,
            "business_id": record.business_id,
            "observed_at": None if record.observed_at is None else record.observed_at.isoformat(),
            "confidence": record.confidence,
            "privacy_class": record.privacy_class,
            "retention_policy": record.retention_policy,
            "lineage_json": _json_dumps(record.lineage),
            "refs_json": _json_dumps(record.refs),
            "payload_json": _json_dumps(record.payload),
            "payload_sha256": record.payload_sha256,
            "evidence_sha256": record.evidence_sha256,
            "labels_json": _json_dumps(record.labels),
            "retention_until": None if record.retention_until is None else record.retention_until.isoformat(),
            "legal_hold": 1 if record.legal_hold else 0,
        }

    @classmethod
    def from_row(
        cls, row: Mapping[str, object], *, allow_legacy_schema: bool = False
    ) -> EvidenceRecord:
        retention_until_raw = row.get("retention_until")
        record = cls(
            evidence_id=str(row.get("evidence_id") or ""),
            tenant_id=str(row.get("tenant_id") or ""),
            scope=str(row.get("scope") or ""),
            run_id=str(row.get("run_id") or ""),
            action_id=None if row.get("action_id") in (None, "") else str(row.get("action_id")),
            action_type=str(row.get("action_type") or ""),
            verification_status=str(row.get("verification_status") or ""),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
            source=str(row.get("source") or "legacy"),
            source_type=str(row.get("source_type") or "legacy"),
            business_id=str(row.get("business_id") or "unknown"),
            observed_at=None if row.get("observed_at") in (None, "") else datetime.fromisoformat(str(row.get("observed_at"))),
            confidence=None if row.get("confidence") in (None, "") else float(row.get("confidence")),
            privacy_class=str(row.get("privacy_class") or "internal"),
            retention_policy=str(row.get("retention_policy") or "legacy"),
            lineage=json.loads(str(row.get("lineage_json") or "{}")),
            refs=tuple(json.loads(str(row.get("refs_json") or "[]"))),
            payload=json.loads(str(row.get("payload_json") or "{}")),
            labels=json.loads(str(row.get("labels_json") or "{}")),
            retention_until=None if retention_until_raw in (None, "") else datetime.fromisoformat(str(retention_until_raw)),
            legal_hold=bool(row.get("legal_hold") or 0),
            schema_version=int(row.get("evidence_schema_version") or 1),
        ).normalized()
        if record.schema_version < EVIDENCE_SCHEMA_VERSION and not allow_legacy_schema:
            raise ValueError("legacy evidence schema requires controlled migration")
        stored_partition_key = str(row.get("partition_key") or "").strip()
        if stored_partition_key and stored_partition_key != record.partition_key:
            raise ValueError("evidence partition key mismatch")
        stored_payload_sha256 = str(row.get("payload_sha256") or "").strip()
        if stored_payload_sha256 and stored_payload_sha256 != record.payload_sha256:
            raise ValueError("evidence payload hash mismatch")
        stored_evidence_sha256 = str(row.get("evidence_sha256") or "").strip()
        if record.schema_version >= EVIDENCE_SCHEMA_VERSION and not stored_evidence_sha256:
            raise ValueError("current evidence record is missing canonical hash")
        if stored_evidence_sha256 and stored_evidence_sha256 != record.evidence_sha256:
            raise ValueError("evidence canonical hash mismatch")
        return record


def _backfill_legacy_evidence_integrity(session: Any) -> None:
    rows = session.fetchall(
        "SELECT * FROM storage_evidence_log WHERE evidence_schema_version = 1"
    )
    if not rows:
        return
    dialect = str(getattr(session, "dialect", "")).strip().lower()
    for raw in rows:
        row = dict(raw)
        legacy = EvidenceRecord.from_row(row, allow_legacy_schema=True)
        upgraded = replace(legacy, schema_version=EVIDENCE_SCHEMA_VERSION).normalized()
        digest = upgraded.evidence_sha256
        if dialect == "postgres":
            session.execute(
                "UPDATE storage_evidence_log SET evidence_schema_version = %s, evidence_sha256 = %s WHERE evidence_id = %s",
                (EVIDENCE_SCHEMA_VERSION, digest, upgraded.evidence_id),
            )
        else:
            session.execute(
                "UPDATE storage_evidence_log SET evidence_schema_version = ?, evidence_sha256 = ? WHERE evidence_id = ?",
                (EVIDENCE_SCHEMA_VERSION, digest, upgraded.evidence_id),
            )


@runtime_checkable
class EvidenceStore(Protocol):
    def append(self, record: EvidenceRecord) -> EvidenceRecord: ...

    def get(self, *, tenant_id: str, evidence_id: str) -> EvidenceRecord | None: ...

    def list_for_tenant(
        self, *, tenant_id: str, run_id: str | None = None, limit: int = 100
    ) -> tuple[EvidenceRecord, ...]: ...

    def delete_expired(self, *, now: datetime | None = None) -> int: ...


class InMemoryEvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, EvidenceRecord] = {}
        self._lock = RLock()

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        with self._lock:
            existing = self._items.get(normalized.evidence_id)
            if existing is not None:
                if existing != normalized:
                    raise ValueError("evidence_id is immutable and already bound to different evidence")
                return existing
            self._items[normalized.evidence_id] = normalized
        return normalized

    def get(self, *, tenant_id: str, evidence_id: str) -> EvidenceRecord | None:
        tenant = _require_evidence_tenant_id(tenant_id)
        with self._lock:
            item = self._items.get(str(evidence_id).strip())
            if item is None or item.tenant_id != tenant:
                return None
            return item

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        normalized_tenant = _require_evidence_tenant_id(tenant_id)
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
            _backfill_legacy_evidence_integrity(session)

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT OR IGNORE INTO storage_evidence_log(
                    evidence_id, evidence_schema_version, tenant_id, partition_key, scope, run_id, action_id, action_type,
                    verification_status, created_at, source, source_type, business_id, observed_at,
                    confidence, privacy_class, retention_policy, lineage_json, refs_json, payload_json, payload_sha256,
                    evidence_sha256, labels_json, retention_until, legal_hold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["evidence_id"], row["evidence_schema_version"], row["tenant_id"], row["partition_key"], row["scope"], row["run_id"], row["action_id"],
                    row["action_type"], row["verification_status"], row["created_at"], row["source"], row["source_type"],
                    row["business_id"], row["observed_at"], row["confidence"], row["privacy_class"], row["retention_policy"],
                    row["lineage_json"], row["refs_json"], row["payload_json"], row["payload_sha256"],
                    row["evidence_sha256"], row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
            stored = session.fetchone(
                "SELECT * FROM storage_evidence_log WHERE evidence_id = ?",
                (normalized.evidence_id,),
            )
        if stored is None:
            raise RuntimeError("evidence append did not persist a record")
        existing = EvidenceRecord.from_row(dict(stored))
        if existing != normalized:
            raise ValueError("evidence_id is immutable and already bound to different evidence")
        return existing

    def get(self, *, tenant_id: str, evidence_id: str) -> EvidenceRecord | None:
        tenant = _require_evidence_tenant_id(tenant_id)
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT * FROM storage_evidence_log WHERE tenant_id = ? AND evidence_id = ?",
                (tenant, str(evidence_id).strip()),
            )
        return None if row is None else EvidenceRecord.from_row(dict(row))

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        tenant = _require_evidence_tenant_id(tenant_id)
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
            _backfill_legacy_evidence_integrity(session)

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        row = normalized.to_row()
        with self._session_factory.open() as session:
            session.execute(
                """
                INSERT INTO storage_evidence_log(
                    evidence_id, evidence_schema_version, tenant_id, partition_key, scope, run_id, action_id, action_type,
                    verification_status, created_at, source, source_type, business_id, observed_at,
                    confidence, privacy_class, retention_policy, lineage_json, refs_json, payload_json, payload_sha256,
                    evidence_sha256, labels_json, retention_until, legal_hold
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (evidence_id) DO NOTHING
                """,
                (
                    row["evidence_id"], row["evidence_schema_version"], row["tenant_id"], row["partition_key"], row["scope"], row["run_id"], row["action_id"],
                    row["action_type"], row["verification_status"], row["created_at"], row["source"], row["source_type"],
                    row["business_id"], row["observed_at"], row["confidence"], row["privacy_class"], row["retention_policy"],
                    row["lineage_json"], row["refs_json"], row["payload_json"], row["payload_sha256"],
                    row["evidence_sha256"], row["labels_json"], row["retention_until"], row["legal_hold"],
                ),
            )
            stored = session.fetchone(
                "SELECT * FROM storage_evidence_log WHERE evidence_id = %s",
                (normalized.evidence_id,),
            )
        if stored is None:
            raise RuntimeError("evidence append did not persist a record")
        existing = EvidenceRecord.from_row(stored)
        if existing != normalized:
            raise ValueError("evidence_id is immutable and already bound to different evidence")
        return existing

    def get(self, *, tenant_id: str, evidence_id: str) -> EvidenceRecord | None:
        tenant = _require_evidence_tenant_id(tenant_id)
        with self._session_factory.open() as session:
            row = session.fetchone(
                "SELECT * FROM storage_evidence_log WHERE tenant_id = %s AND evidence_id = %s",
                (tenant, str(evidence_id).strip()),
            )
        return None if row is None else EvidenceRecord.from_row(row)

    def list_for_tenant(self, *, tenant_id: str, run_id: str | None = None, limit: int = 100) -> tuple[EvidenceRecord, ...]:
        tenant = _require_evidence_tenant_id(tenant_id)
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
        moment = (now or utc_now()).astimezone(UTC).isoformat()
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
    "CANON_STORAGE_EVIDENCE_RECORD_EXPLICIT_LEGACY_FACTORY",
    "EVIDENCE_LINEAGE_STAGES",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceRecord",
    "EvidenceStore",
    "InMemoryEvidenceStore",
    "SqliteEvidenceStore",
    "PostgresEvidenceStore",
]
