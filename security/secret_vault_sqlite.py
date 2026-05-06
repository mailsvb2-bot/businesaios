from __future__ import annotations

import hashlib
import json
import secrets
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from security.secret_contract import SecretRecord, SecretRef, SecretSource, SecretState, utc_now
from security.secret_vault_backend import (
    SecretEnvelope,
    SecretLookup,
    SecretVaultBackend,
    envelope_is_active,
    to_metadata_with_key_binding,
)


CANON_SECRET_VAULT_SQLITE = True


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


def _norm(value: str | None) -> str:
    token = str(value or "").strip()
    return token if token else "-"


def _denorm(value: str | None) -> str | None:
    token = str(value or "").strip()
    return None if token in {"", "-"} else token


def _ref_identity(ref: SecretRef) -> tuple[str, str, str, str, str]:
    ref.validate()
    return (ref.tenant_id, ref.secret_name, _norm(ref.connector_id), _norm(ref.scope), ref.version)


def _calc_etag(*, ciphertext: bytes, encryption_key_id: str, version_nonce: str) -> str:
    digest = hashlib.sha256()
    digest.update(bytes(ciphertext))
    digest.update(b"|")
    digest.update(str(encryption_key_id).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(version_nonce).encode("utf-8"))
    return digest.hexdigest()


def _row_to_envelope(row: Any) -> SecretEnvelope:
    ref = SecretRef(
        tenant_id=str(row["tenant_id"]),
        secret_name=str(row["secret_name"]),
        version=str(row["version"]),
        connector_id=_denorm(cast(str | None, row["connector_id_norm"])),
        scope=_denorm(cast(str | None, row["scope_norm"])),
    )
    record = SecretRecord(
        ref=ref,
        ciphertext=bytes.fromhex(str(row["ciphertext_hex"])),
        source=SecretSource(str(row["source"])),
        created_at=cast(datetime, _from_iso(cast(str | None, row["created_at"]))),
        updated_at=cast(datetime, _from_iso(cast(str | None, row["updated_at"]))),
        rotated_at=_from_iso(cast(str | None, row["rotated_at"])),
        deleted_at=_from_iso(cast(str | None, row["deleted_at"])),
        expires_at=_from_iso(cast(str | None, row["expires_at"])),
        state=SecretState(str(row["state"])),
        metadata=dict(json.loads(str(row["metadata_json"] or "{}"))),
    )
    envelope = SecretEnvelope(
        record=record,
        encryption_key_id=str(row["encryption_key_id"]),
        version_nonce=str(row["version_nonce"]),
        row_version=int(row["row_version"]),
        etag=str(row["etag"]) if row["etag"] not in {None, ""} else None,
        metadata=dict(json.loads(str(row["envelope_metadata_json"] or "{}"))),
    )
    envelope.validate()
    return envelope


def _envelope_to_params(envelope: SecretEnvelope) -> dict[str, object]:
    envelope.validate()
    record = envelope.record
    etag = envelope.etag or _calc_etag(
        ciphertext=bytes(record.ciphertext),
        encryption_key_id=envelope.encryption_key_id,
        version_nonce=envelope.version_nonce,
    )
    return {
        "tenant_id": record.ref.tenant_id,
        "secret_name": record.ref.secret_name,
        "connector_id_norm": _norm(record.ref.connector_id),
        "scope_norm": _norm(record.ref.scope),
        "version": record.ref.version,
        "ciphertext_hex": bytes(record.ciphertext).hex(),
        "source": record.source.value,
        "state": record.state.value,
        "created_at": _to_iso(record.created_at),
        "updated_at": _to_iso(record.updated_at),
        "rotated_at": _to_iso(record.rotated_at),
        "deleted_at": _to_iso(record.deleted_at),
        "expires_at": _to_iso(record.expires_at),
        "metadata_json": json.dumps(dict(record.metadata or {}), ensure_ascii=False, sort_keys=True),
        "encryption_key_id": envelope.encryption_key_id,
        "version_nonce": envelope.version_nonce,
        "row_version": int(envelope.row_version),
        "etag": etag,
        "envelope_metadata_json": json.dumps(dict(envelope.metadata or {}), ensure_ascii=False, sort_keys=True),
    }


class SqliteSecretVaultBackend(SecretVaultBackend):
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
                CREATE TABLE IF NOT EXISTS security_secret_vault (
                    tenant_id TEXT NOT NULL,
                    secret_name TEXT NOT NULL,
                    connector_id_norm TEXT NOT NULL,
                    scope_norm TEXT NOT NULL,
                    version TEXT NOT NULL,
                    ciphertext_hex TEXT NOT NULL,
                    source TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    rotated_at TEXT NULL,
                    deleted_at TEXT NULL,
                    expires_at TEXT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    encryption_key_id TEXT NOT NULL,
                    version_nonce TEXT NOT NULL,
                    row_version INTEGER NOT NULL DEFAULT 1,
                    etag TEXT NOT NULL,
                    envelope_metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, secret_name, connector_id_norm, scope_norm, version)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_secret_vault_lookup
                ON security_secret_vault (tenant_id, secret_name, connector_id_norm, scope_norm, updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_secret_vault_key_binding
                ON security_secret_vault (encryption_key_id, tenant_id, connector_id_norm, updated_at DESC)
                """
            )
            conn.commit()

    def put(self, envelope: SecretEnvelope, *, expected_row_version: int | None = None) -> SecretEnvelope:
        envelope.validate()
        params = _envelope_to_params(envelope)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            existing = conn.execute(
                """
                SELECT row_version FROM security_secret_vault
                WHERE tenant_id = ? AND secret_name = ? AND connector_id_norm = ? AND scope_norm = ? AND version = ?
                """,
                _ref_identity(envelope.record.ref),
            ).fetchone()
            if existing is None:
                if expected_row_version not in {None, 0}:
                    raise RuntimeError("secret row missing for expected_row_version update")
                conn.execute(
                    """
                    INSERT INTO security_secret_vault (
                        tenant_id, secret_name, connector_id_norm, scope_norm, version,
                        ciphertext_hex, source, state, created_at, updated_at, rotated_at, deleted_at,
                        expires_at, metadata_json, encryption_key_id, version_nonce, row_version, etag, envelope_metadata_json
                    ) VALUES (
                        :tenant_id, :secret_name, :connector_id_norm, :scope_norm, :version,
                        :ciphertext_hex, :source, :state, :created_at, :updated_at, :rotated_at, :deleted_at,
                        :expires_at, :metadata_json, :encryption_key_id, :version_nonce, 1, :etag, :envelope_metadata_json
                    )
                    """,
                    params,
                )
            else:
                current_row_version = int(existing["row_version"])
                if expected_row_version is not None and current_row_version != int(expected_row_version):
                    raise RuntimeError(f"secret row_version conflict: expected {expected_row_version}, got {current_row_version}")
                conn.execute(
                    """
                    UPDATE security_secret_vault
                    SET ciphertext_hex = :ciphertext_hex,
                        source = :source,
                        state = :state,
                        created_at = :created_at,
                        updated_at = :updated_at,
                        rotated_at = :rotated_at,
                        deleted_at = :deleted_at,
                        expires_at = :expires_at,
                        metadata_json = :metadata_json,
                        encryption_key_id = :encryption_key_id,
                        version_nonce = :version_nonce,
                        row_version = row_version + 1,
                        etag = :etag,
                        envelope_metadata_json = :envelope_metadata_json
                    WHERE tenant_id = :tenant_id
                      AND secret_name = :secret_name
                      AND connector_id_norm = :connector_id_norm
                      AND scope_norm = :scope_norm
                      AND version = :version
                    """,
                    params,
                )
            conn.commit()
            row = conn.execute(
                """
                SELECT * FROM security_secret_vault
                WHERE tenant_id = ? AND secret_name = ? AND connector_id_norm = ? AND scope_norm = ? AND version = ?
                """,
                _ref_identity(envelope.record.ref),
            ).fetchone()
        if row is None:
            raise RuntimeError("secret vault write lost after commit")
        return _row_to_envelope(row)

    def get(self, ref: SecretRef) -> SecretEnvelope:
        ref.validate()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM security_secret_vault
                WHERE tenant_id = ? AND secret_name = ? AND connector_id_norm = ? AND scope_norm = ? AND version = ?
                """,
                _ref_identity(ref),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown secret ref: {ref.key()}")
        return _row_to_envelope(row)

    def get_latest(self, lookup: SecretLookup) -> SecretEnvelope:
        rows = self.list_versions(lookup)
        if not rows:
            raise KeyError(f"secret not found for tenant_id={lookup.tenant_id!r} secret_name={lookup.secret_name!r}")
        return rows[0]

    def list_versions(self, lookup: SecretLookup) -> tuple[SecretEnvelope, ...]:
        lookup.validate()
        with self._lock, self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT * FROM security_secret_vault
                    WHERE tenant_id = ? AND secret_name = ? AND connector_id_norm = ? AND scope_norm = ?
                      AND (? IS NULL OR version = ?)
                    ORDER BY updated_at DESC, row_version DESC, version DESC
                    """,
                    (
                        lookup.tenant_id,
                        lookup.secret_name,
                        _norm(lookup.connector_id),
                        _norm(lookup.scope),
                        None if lookup.version is None else lookup.version,
                        None if lookup.version is None else lookup.version,
                    ),
                ).fetchall()
            )
        envelopes = tuple(_row_to_envelope(row) for row in rows)
        if lookup.include_inactive:
            return envelopes
        moment = lookup.as_of or utc_now()
        return tuple(env for env in envelopes if envelope_is_active(env, at=moment))

    def list_by_encryption_key_id(self, *, encryption_key_id: str, tenant_id: str | None = None, connector_id: str | None = None, limit: int = 500) -> tuple[SecretEnvelope, ...]:
        if not str(encryption_key_id or "").strip():
            raise ValueError("encryption_key_id is required")
        if int(limit) <= 0:
            raise ValueError("limit must be > 0")
        with self._lock, self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT * FROM security_secret_vault
                    WHERE encryption_key_id = ?
                      AND (? = 0 OR tenant_id = ?)
                      AND (? = 0 OR connector_id_norm = ?)
                    ORDER BY updated_at DESC, row_version DESC
                    LIMIT ?
                    """,
                    (
                        str(encryption_key_id),
                        1 if tenant_id is not None else 0,
                        tenant_id,
                        1 if connector_id is not None else 0,
                        _norm(connector_id),
                        int(limit),
                    ),
                ).fetchall()
            )
        return tuple(_row_to_envelope(row) for row in rows)

    def deactivate(self, ref: SecretRef, *, compromised: bool = False, now: datetime | None = None) -> SecretEnvelope:
        current = self.get(ref)
        moment = now or utc_now()
        updated_record = current.record.disable(now=moment, compromised=compromised)
        return self.put(
            SecretEnvelope(
                record=updated_record,
                encryption_key_id=current.encryption_key_id,
                version_nonce=current.version_nonce,
                row_version=current.row_version,
                etag=current.etag,
                metadata=dict(current.metadata or {}),
            ),
            expected_row_version=current.row_version,
        )

    def soft_delete(self, ref: SecretRef, *, now: datetime | None = None) -> SecretEnvelope:
        current = self.get(ref)
        moment = now or utc_now()
        updated_record = current.record.soft_delete(now=moment)
        return self.put(
            SecretEnvelope(
                record=updated_record,
                encryption_key_id=current.encryption_key_id,
                version_nonce=current.version_nonce,
                row_version=current.row_version,
                etag=current.etag,
                metadata=dict(current.metadata or {}),
            ),
            expected_row_version=current.row_version,
        )

    def rekey(self, *, ref: SecretRef, ciphertext: bytes, encryption_key_id: str, now: datetime | None = None, expected_row_version: int | None = None) -> SecretEnvelope:
        current = self.get(ref)
        moment = now or utc_now()
        updated_record = replace(
            current.record,
            ciphertext=bytes(ciphertext),
            updated_at=moment,
            rotated_at=moment,
            metadata=to_metadata_with_key_binding(
                current.record.metadata,
                encryption_key_id=encryption_key_id,
                version_nonce=current.version_nonce,
            ),
        )
        return self.put(
            SecretEnvelope(
                record=updated_record,
                encryption_key_id=str(encryption_key_id),
                version_nonce=current.version_nonce,
                row_version=current.row_version,
                metadata={
                    **dict(current.metadata or {}),
                    "rekeyed_at": moment.isoformat(),
                    "rekeyed_from_encryption_key_id": current.encryption_key_id,
                },
            ),
            expected_row_version=current.row_version if expected_row_version is None else expected_row_version,
        )

    def seed_encrypted(self, *, ref: SecretRef, ciphertext: bytes, encryption_key_id: str, source: SecretSource = SecretSource.VAULT, metadata: dict[str, str] | None = None, expires_at: datetime | None = None) -> SecretEnvelope:
        now = utc_now()
        version_nonce = secrets.token_hex(16)
        record = SecretRecord(
            ref=ref,
            ciphertext=bytes(ciphertext),
            source=source,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            state=SecretState.ACTIVE,
            metadata=to_metadata_with_key_binding(metadata, encryption_key_id=encryption_key_id, version_nonce=version_nonce),
        )
        return self.put(
            SecretEnvelope(record=record, encryption_key_id=str(encryption_key_id), version_nonce=version_nonce, row_version=1, metadata={}),
            expected_row_version=0,
        )


__all__ = ["CANON_SECRET_VAULT_SQLITE", "SqliteSecretVaultBackend"]
