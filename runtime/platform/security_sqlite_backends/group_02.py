from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

from runtime.platform.security_sqlite_backends.common import _connect, _ensure_parent


class SQLiteReencryptionProgressLedgerBackend:
    def __init__(self, db_path: str, event_cls: type) -> None:
        self._db_path = str(db_path)
        self._event_cls = event_cls
        self.ensure_schema()
    def append(self, event: Any) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO security_reencryption_progress(job_id, event_kind, secret_ref, ok, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)", (event.job_id, event.event_kind, event.secret_ref, 1 if event.ok else 0, json.dumps(event.payload, ensure_ascii=False, sort_keys=True), int(time.time())))
            conn.commit()
    def latest_for_job(self, job_id: str, *, limit: int = 100) -> tuple[Any, ...]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT job_id, event_kind, secret_ref, ok, payload_json FROM security_reencryption_progress WHERE job_id = ? ORDER BY rowid DESC LIMIT ?", (str(job_id), int(limit))).fetchall()
        return tuple(self._event_cls(job_id=str(r[0]), event_kind=str(r[1]), secret_ref=r[2], ok=bool(int(r[3])), payload=dict(json.loads(str(r[4] or "{}")))) for r in rows)
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_reencryption_progress (job_id TEXT NOT NULL, event_kind TEXT NOT NULL, secret_ref TEXT NULL, ok INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()

class SQLiteKeyRotationJournalBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def append(self, *, key_id: str, old_status: str, new_status: str, payload: Mapping[str, Any]) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO key_rotation_journal(key_id, old_status, new_status, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?)", (str(key_id), str(old_status), str(new_status), json.dumps(dict(payload), ensure_ascii=False), int(time.time())))
            conn.commit()
    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT key_id, old_status, new_status, payload_json, created_at_epoch_s FROM key_rotation_journal ORDER BY journal_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"key_id": str(r[0]), "old_status": str(r[1]), "new_status": str(r[2]), "payload": json.loads(str(r[3])), "created_at_epoch_s": int(r[4])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS key_rotation_journal (journal_id INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL, old_status TEXT NOT NULL, new_status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()

class SQLiteSecurityIncidentRegistryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def open_incident(self, *, incident_kind: str, payload: Mapping[str, Any]) -> int:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("INSERT INTO security_incidents(incident_kind, status, payload_json, created_at_epoch_s, resolved_at_epoch_s) VALUES(?, 'open', ?, ?, NULL)", (str(incident_kind), json.dumps(dict(payload), ensure_ascii=False), int(time.time())))
            conn.commit()
            return int(cursor.lastrowid)
    def resolve(self, *, incident_id: int, resolution_payload: Mapping[str, Any] | None = None) -> bool:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("UPDATE security_incidents SET status = 'resolved', resolution_payload_json = ?, resolved_at_epoch_s = ? WHERE incident_id = ? AND status = 'open'", (json.dumps(dict(resolution_payload or {}), ensure_ascii=False), int(time.time()), int(incident_id)))
            conn.commit()
            return int(cursor.rowcount) > 0
    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT incident_id, incident_kind, status, payload_json, resolution_payload_json, created_at_epoch_s, resolved_at_epoch_s FROM security_incidents ORDER BY incident_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"incident_id": int(r[0]), "incident_kind": str(r[1]), "status": str(r[2]), "payload": json.loads(str(r[3])), "resolution_payload": json.loads(str(r[4] or "{}")), "created_at_epoch_s": int(r[5]), "resolved_at_epoch_s": None if r[6] is None else int(r[6])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_incidents (incident_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_kind TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, resolution_payload_json TEXT NULL, created_at_epoch_s INTEGER NOT NULL, resolved_at_epoch_s INTEGER NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_incidents_status_created ON security_incidents(status, created_at_epoch_s)")
            conn.commit()

class SQLiteApprovalReplayGuardBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def consume(self, *, approval_id: str, operation_kind: str, actor: str) -> bool:
        with _connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?", (str(approval_id),)).fetchone() is not None:
                conn.rollback()
                return False
            conn.execute("INSERT INTO consumed_operator_approvals(approval_id, operation_kind, actor, consumed_at_epoch_s) VALUES(?, ?, ?, ?)", (str(approval_id), str(operation_kind), str(actor), int(time.time())))
            conn.commit()
            return True
    def has_been_consumed(self, *, approval_id: str) -> bool:
        with _connect(self._db_path) as conn:
            return conn.execute("SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?", (str(approval_id),)).fetchone() is not None
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS consumed_operator_approvals (approval_id TEXT PRIMARY KEY, operation_kind TEXT NOT NULL, actor TEXT NOT NULL, consumed_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()

class SQLiteSecurityQuarantineRegistryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def quarantine(self, *, entity_kind: str, entity_id: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO security_quarantine(entity_kind, entity_id, reason, payload_json, quarantined_at_epoch_s, released_at_epoch_s) VALUES(?, ?, ?, ?, ?, NULL)", (str(entity_kind), str(entity_id), str(reason), json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time())))
            conn.commit()
    def release(self, *, entity_kind: str, entity_id: str) -> bool:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("UPDATE security_quarantine SET released_at_epoch_s = ? WHERE entity_kind = ? AND entity_id = ? AND released_at_epoch_s IS NULL", (int(time.time()), str(entity_kind), str(entity_id)))
            conn.commit()
            return int(cursor.rowcount) > 0
    def is_quarantined(self, *, entity_kind: str, entity_id: str) -> bool:
        with _connect(self._db_path) as conn:
            return conn.execute("SELECT entity_id FROM security_quarantine WHERE entity_kind = ? AND entity_id = ? AND released_at_epoch_s IS NULL", (str(entity_kind), str(entity_id))).fetchone() is not None
    def count_active(self, *, entity_kind: str | None = None) -> int:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM security_quarantine WHERE released_at_epoch_s IS NULL" if entity_kind is None else "SELECT COUNT(*) FROM security_quarantine WHERE entity_kind = ? AND released_at_epoch_s IS NULL", () if entity_kind is None else (str(entity_kind),)).fetchone()
        return int(row[0] if row else 0)
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_quarantine (entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL, reason TEXT NOT NULL, payload_json TEXT NOT NULL, quarantined_at_epoch_s INTEGER NOT NULL, released_at_epoch_s INTEGER NULL, PRIMARY KEY(entity_kind, entity_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_quarantine_active ON security_quarantine(entity_kind, released_at_epoch_s)")
            conn.commit()

class SQLiteReencryptionJobStoreBackend:
    def __init__(self, db_path: str, job_cls: type) -> None:
        self._db_path = str(db_path)
        self._job_cls = job_cls
        self.ensure_schema()
    def put(self, job: Any) -> Any:
        with _connect(self._db_path) as conn:
            conn.execute("""INSERT INTO security_reencryption_jobs(job_id, old_key_id, new_key_id, tenant_id, connector_id, status, cursor_secret_ref, processed_count, failed_count, metadata_json, updated_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET old_key_id=excluded.old_key_id, new_key_id=excluded.new_key_id, tenant_id=excluded.tenant_id, connector_id=excluded.connector_id, status=excluded.status, cursor_secret_ref=excluded.cursor_secret_ref, processed_count=excluded.processed_count, failed_count=excluded.failed_count, metadata_json=excluded.metadata_json, updated_at_epoch_s=excluded.updated_at_epoch_s""", (job.job_id, job.old_key_id, job.new_key_id, job.tenant_id, job.connector_id, job.status, job.cursor_secret_ref, int(job.processed_count), int(job.failed_count), json.dumps(job.metadata or {}, ensure_ascii=False, sort_keys=True), int(time.time())))
            conn.commit()
        return job
    def _row(self, r: tuple[Any, ...]) -> Any:
        return self._job_cls(job_id=str(r[0]), old_key_id=str(r[1]), new_key_id=str(r[2]), tenant_id=r[3], connector_id=r[4], status=str(r[5]), cursor_secret_ref=r[6], processed_count=int(r[7]), failed_count=int(r[8]), metadata=dict(json.loads(str(r[9] or "{}"))))
    def get(self, job_id: str) -> Any:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT job_id, old_key_id, new_key_id, tenant_id, connector_id, status, cursor_secret_ref, processed_count, failed_count, metadata_json FROM security_reencryption_jobs WHERE job_id = ?", (str(job_id),)).fetchone()
        if row is None:
            raise KeyError(f"unknown reencryption job: {job_id}")
        return self._row(tuple(row))
    def list_active(self) -> tuple[Any, ...]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT job_id FROM security_reencryption_jobs WHERE status IN ('pending', 'running', 'paused') ORDER BY updated_at_epoch_s ASC, job_id ASC").fetchall()
        return tuple(self.get(str(r[0])) for r in rows)
    def list_active_for_tenant(self, *, tenant_id: str) -> tuple[Any, ...]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT job_id FROM security_reencryption_jobs WHERE tenant_id = ? AND status IN ('pending', 'running', 'paused') ORDER BY updated_at_epoch_s ASC, job_id ASC", (str(tenant_id).strip(),)).fetchall()
        return tuple(self.get(str(r[0])) for r in rows)
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_reencryption_jobs (job_id TEXT PRIMARY KEY, old_key_id TEXT NOT NULL, new_key_id TEXT NOT NULL, tenant_id TEXT NULL, connector_id TEXT NULL, status TEXT NOT NULL, cursor_secret_ref TEXT NULL, processed_count INTEGER NOT NULL, failed_count INTEGER NOT NULL, metadata_json TEXT NOT NULL, updated_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()

__all__ = [
    "SQLiteReencryptionProgressLedgerBackend",
    "SQLiteKeyRotationJournalBackend",
    "SQLiteSecurityIncidentRegistryBackend",
    "SQLiteApprovalReplayGuardBackend",
    "SQLiteSecurityQuarantineRegistryBackend",
    "SQLiteReencryptionJobStoreBackend",
]
