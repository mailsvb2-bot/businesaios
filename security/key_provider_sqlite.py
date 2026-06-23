from __future__ import annotations

import base64
import json
import secrets
import threading
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus, utc_now
from security.key_provider_contracts import KeyProvider
from security.key_provider_backend import (
    KeyProviderBackend,
    KeyQuery,
    KeyRotationCandidate,
    KeyScope,
    KeyStatusChange,
    build_rotation_candidate,
    select_best_active_key,
)


CANON_KEY_PROVIDER_SQLITE = True


def _sqlite3() -> Any:
    return __import__("sqlite3")


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require_aware(value, field_name="datetime")
    return value.isoformat()


def _from_iso(value: str | None) -> datetime | None:
    if value in {None, ""}:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    _require_aware(parsed, field_name="parsed datetime")
    return parsed


def _normalize_scope_token(value: str | None) -> str:
    token = str(value or "").strip()
    return token if token else "-"


def _denormalize_scope_token(value: str | None) -> str | None:
    token = str(value or "").strip()
    return None if token in {"", "-"} else token


def _record_to_row(record: KeyMaterialRecord) -> dict[str, object]:
    record.validate()
    return {
        "key_id": record.key_id,
        "purpose": record.purpose.value,
        "secret_b64": base64.b64encode(bytes(record.secret_bytes)).decode("ascii"),
        "tenant_id_norm": _normalize_scope_token(record.tenant_id),
        "connector_id_norm": _normalize_scope_token(record.connector_id),
        "tenant_id": record.tenant_id,
        "connector_id": record.connector_id,
        "status": record.status.value,
        "created_at": _to_iso(record.created_at),
        "activated_at": _to_iso(record.activated_at),
        "expires_at": _to_iso(record.expires_at),
        "metadata_json": json.dumps(dict(record.metadata or {}), ensure_ascii=False, sort_keys=True),
    }


def _row_to_record(row: Any) -> KeyMaterialRecord:
    record = KeyMaterialRecord(
        key_id=str(row["key_id"]),
        purpose=KeyPurpose(str(row["purpose"])),
        secret_bytes=base64.b64decode(str(row["secret_b64"])),
        tenant_id=_denormalize_scope_token(cast(str | None, row["tenant_id_norm"])),
        connector_id=_denormalize_scope_token(cast(str | None, row["connector_id_norm"])),
        status=KeyStatus(str(row["status"])),
        created_at=cast(datetime, _from_iso(cast(str | None, row["created_at"]))),
        activated_at=cast(datetime, _from_iso(cast(str | None, row["activated_at"]))),
        expires_at=_from_iso(cast(str | None, row["expires_at"])),
        metadata=dict(json.loads(str(row["metadata_json"] or "{}"))),
    )
    record.validate()
    return record


class SqliteKeyProviderBackend(KeyProviderBackend):
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path)
        self._busy_timeout_ms = max(0, int(busy_timeout_ms))
        self._lock = threading.RLock()
        self._init_db()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> Any:
        sqlite3 = _sqlite3()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path), timeout=max(1.0, self._busy_timeout_ms / 1000.0), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms};")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_keys (
                    key_id TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    secret_b64 TEXT NOT NULL,
                    tenant_id_norm TEXT NOT NULL,
                    connector_id_norm TEXT NOT NULL,
                    tenant_id TEXT NULL,
                    connector_id TEXT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT NOT NULL,
                    expires_at TEXT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_keys_scope
                ON security_keys (purpose, tenant_id_norm, connector_id_norm, status, activated_at DESC, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_security_keys_single_active
                ON security_keys (purpose, tenant_id_norm, connector_id_norm)
                WHERE status = 'active'
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_keys_expires ON security_keys (expires_at)")
            conn.commit()

    def upsert(self, record: KeyMaterialRecord) -> KeyMaterialRecord:
        payload = _record_to_row(record)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO security_keys (
                    key_id, purpose, secret_b64, tenant_id_norm, connector_id_norm,
                    tenant_id, connector_id, status, created_at, activated_at, expires_at, metadata_json
                ) VALUES (
                    :key_id, :purpose, :secret_b64, :tenant_id_norm, :connector_id_norm,
                    :tenant_id, :connector_id, :status, :created_at, :activated_at, :expires_at, :metadata_json
                )
                ON CONFLICT(key_id) DO UPDATE SET
                    purpose=excluded.purpose,
                    secret_b64=excluded.secret_b64,
                    tenant_id_norm=excluded.tenant_id_norm,
                    connector_id_norm=excluded.connector_id_norm,
                    tenant_id=excluded.tenant_id,
                    connector_id=excluded.connector_id,
                    status=excluded.status,
                    created_at=excluded.created_at,
                    activated_at=excluded.activated_at,
                    expires_at=excluded.expires_at,
                    metadata_json=excluded.metadata_json
                """,
                payload,
            )
            conn.commit()
        return record

    def get(self, key_id: str) -> KeyMaterialRecord:
        if not str(key_id or "").strip():
            raise ValueError("key_id is required")
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM security_keys WHERE key_id = ?", (str(key_id),)).fetchone()
        if row is None:
            raise KeyError(f"unknown key_id: {key_id}")
        return _row_to_record(row)

    def list(self, query: KeyQuery) -> tuple[KeyMaterialRecord, ...]:
        query.validate()
        with self._lock, self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT * FROM security_keys
                    WHERE purpose = ? AND tenant_id_norm = ? AND connector_id_norm = ?
                    ORDER BY CASE status WHEN 'active' THEN 1 ELSE 0 END DESC, activated_at DESC, created_at DESC, key_id DESC
                    """,
                    (
                        query.scope.purpose.value,
                        _normalize_scope_token(query.scope.tenant_id),
                        _normalize_scope_token(query.scope.connector_id),
                    ),
                ).fetchall()
            )
        records = tuple(_row_to_record(row) for row in rows)
        if query.include_inactive:
            return records
        moment = query.as_of or utc_now()
        return tuple(record for record in records if record.is_usable(at=moment))

    def get_active(self, query: KeyQuery) -> KeyMaterialRecord:
        return select_best_active_key(
            self.list(KeyQuery(scope=query.scope, include_inactive=True, as_of=query.as_of)),
            query=query,
        )

    def apply_status_change(self, change: KeyStatusChange) -> KeyMaterialRecord:
        change.validate()
        current = self.get(change.key_id)
        if current.status is not change.from_status:
            raise ValueError(
                f"status mismatch for key_id={change.key_id}: expected {change.from_status.value}, got {current.status.value}"
            )
        updated = replace(
            current,
            status=change.to_status,
            metadata={
                **dict(current.metadata or {}),
                **dict(change.metadata_patch or {}),
                "status_changed_at": change.changed_at.isoformat(),
                "status_changed_from": change.from_status.value,
                "status_changed_to": change.to_status.value,
            },
        )
        return self.upsert(updated)

    def rotate(self, *, old_key_id: str, new_record: KeyMaterialRecord, rotated_at: datetime | None = None) -> tuple[KeyMaterialRecord, KeyMaterialRecord]:
        old_record = self.get(old_key_id)
        if old_record.purpose is not new_record.purpose:
            raise ValueError("rotation must preserve purpose")
        if old_record.tenant_id != new_record.tenant_id:
            raise ValueError("rotation must preserve tenant_id")
        if old_record.connector_id != new_record.connector_id:
            raise ValueError("rotation must preserve connector_id")
        if old_record.key_id == new_record.key_id:
            raise ValueError("new key_id must differ from old key_id")
        moment = rotated_at or utc_now()
        _require_aware(moment, field_name="rotated_at")
        old_updated = replace(
            old_record,
            status=KeyStatus.DEPRECATED,
            metadata={**dict(old_record.metadata or {}), "rotated_to_key_id": new_record.key_id, "rotated_at": moment.isoformat()},
        )
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                "UPDATE security_keys SET status = ?, metadata_json = ? WHERE key_id = ?",
                (
                    old_updated.status.value,
                    json.dumps(dict(old_updated.metadata or {}), ensure_ascii=False, sort_keys=True),
                    old_record.key_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO security_keys (
                    key_id, purpose, secret_b64, tenant_id_norm, connector_id_norm,
                    tenant_id, connector_id, status, created_at, activated_at, expires_at, metadata_json
                ) VALUES (
                    :key_id, :purpose, :secret_b64, :tenant_id_norm, :connector_id_norm,
                    :tenant_id, :connector_id, :status, :created_at, :activated_at, :expires_at, :metadata_json
                )
                """,
                _record_to_row(new_record),
            )
            conn.commit()
        return old_updated, new_record

    def list_due_for_rotation(self, *, max_age: timedelta, now: datetime | None = None, limit: int = 100) -> tuple[KeyRotationCandidate, ...]:
        moment = now or utc_now()
        _require_aware(moment, field_name="now")
        if int(limit) <= 0:
            raise ValueError("limit must be > 0")
        with self._lock, self._connect() as conn:
            rows = list(
                conn.execute(
                    "SELECT * FROM security_keys WHERE status IN (?, ?) ORDER BY created_at ASC, key_id ASC LIMIT ?",
                    (KeyStatus.ACTIVE.value, KeyStatus.DEPRECATED.value, int(limit) * 8),
                ).fetchall()
            )
        out: list[KeyRotationCandidate] = []
        for row in rows:
            candidate = build_rotation_candidate(record=_row_to_record(row), max_age=max_age, now=moment)
            if candidate is not None:
                out.append(candidate)
            if len(out) >= int(limit):
                break
        return tuple(out)


class SqliteKeyProvider(KeyProvider):
    def __init__(self, backend: SqliteKeyProviderBackend) -> None:
        self._backend = backend

    def issue_key(self, *, key_id: str, purpose: KeyPurpose, tenant_id: str | None = None, connector_id: str | None = None, expires_in_seconds: int | None = None) -> KeyMaterialRecord:
        expires_at = None
        if expires_in_seconds is not None:
            ttl = int(expires_in_seconds)
            if ttl <= 0:
                raise ValueError("expires_in_seconds must be > 0")
            expires_at = utc_now() + timedelta(seconds=ttl)
        record = KeyMaterialRecord(
            key_id=str(key_id).strip(),
            purpose=purpose,
            secret_bytes=secrets.token_bytes(32),
            tenant_id=tenant_id,
            connector_id=connector_id,
            expires_at=expires_at,
        )
        return self._backend.upsert(record)

    def register(self, record: KeyMaterialRecord) -> None:
        self._backend.upsert(record)

    def get(self, key_id: str) -> KeyMaterialRecord:
        return self._backend.get(key_id)

    def get_active_for(self, *, purpose: KeyPurpose, tenant_id: str | None = None, connector_id: str | None = None, at: datetime | None = None) -> KeyMaterialRecord:
        return self._backend.get_active(
            KeyQuery(scope=KeyScope(purpose=purpose, tenant_id=tenant_id, connector_id=connector_id), as_of=at)
        )

    def revoke(self, key_id: str) -> KeyMaterialRecord:
        current = self.get(key_id)
        return self._backend.apply_status_change(
            KeyStatusChange(key_id=key_id, from_status=current.status, to_status=KeyStatus.REVOKED, changed_at=utc_now())
        )

    def compromise(self, key_id: str) -> KeyMaterialRecord:
        current = self.get(key_id)
        return self._backend.apply_status_change(
            KeyStatusChange(key_id=key_id, from_status=current.status, to_status=KeyStatus.COMPROMISED, changed_at=utc_now())
        )

    def rotate(self, *, current_key_id: str, new_key_id: str, expires_in_seconds: int | None = None) -> KeyMaterialRecord:
        current = self.get(current_key_id)
        expires_at = None
        if expires_in_seconds is not None:
            ttl = int(expires_in_seconds)
            if ttl <= 0:
                raise ValueError("expires_in_seconds must be > 0")
            expires_at = utc_now() + timedelta(seconds=ttl)
        new_record = KeyMaterialRecord(
            key_id=str(new_key_id).strip(),
            purpose=current.purpose,
            secret_bytes=secrets.token_bytes(32),
            tenant_id=current.tenant_id,
            connector_id=current.connector_id,
            expires_at=expires_at,
            metadata={**dict(current.metadata or {}), "rotation_parent_key_id": current.key_id},
        )
        _, rotated = self._backend.rotate(old_key_id=current_key_id, new_record=new_record)
        return rotated


__all__ = ["CANON_KEY_PROVIDER_SQLITE", "SqliteKeyProvider", "SqliteKeyProviderBackend"]
