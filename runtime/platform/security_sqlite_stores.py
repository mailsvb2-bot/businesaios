from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping

CANON_PLATFORM_SECURITY_SQLITE_STORES = True


def _ensure_parent(db_path: str) -> None:
    Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


class SQLiteGovernanceJournalStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def append(self, *, event_kind: str, entity_kind: str, entity_id: str, payload: Mapping[str, Any], related_incident_id: int | None = None, related_approval_id: str | None = None, related_drill_kind: str | None = None) -> dict[str, Any]:
        now = int(time.time())
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with _connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO governance_journal(
                    event_kind, entity_kind, entity_id, payload_json,
                    related_incident_id, related_approval_id, related_drill_kind, created_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(event_kind), str(entity_kind), str(entity_id), payload_json, None if related_incident_id is None else int(related_incident_id), None if related_approval_id is None else str(related_approval_id), None if related_drill_kind is None else str(related_drill_kind), now),
            )
            conn.commit()
            return {"journal_id": int(cursor.lastrowid), "created_at_epoch_s": now}

    def latest(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT journal_id, event_kind, entity_kind, entity_id, payload_json,
                       related_incident_id, related_approval_id, related_drill_kind, created_at_epoch_s
                FROM governance_journal ORDER BY journal_id DESC LIMIT ?
                """,
                (max(int(limit), 1),),
            ).fetchall()
        return [{"journal_id": int(r[0]), "event_kind": str(r[1]), "entity_kind": str(r[2]), "entity_id": str(r[3]), "payload": json.loads(str(r[4])), "related_incident_id": None if r[5] is None else int(r[5]), "related_approval_id": None if r[6] is None else str(r[6]), "related_drill_kind": None if r[7] is None else str(r[7]), "created_at_epoch_s": int(r[8])} for r in rows]

    def latest_entity_timeline(self, *, entity_kind: str, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT journal_id, event_kind, payload_json, related_incident_id,
                       related_approval_id, related_drill_kind, created_at_epoch_s
                FROM governance_journal WHERE entity_kind = ? AND entity_id = ? ORDER BY journal_id DESC LIMIT ?
                """,
                (str(entity_kind), str(entity_id), max(int(limit), 1)),
            ).fetchall()
        return [{"journal_id": int(r[0]), "event_kind": str(r[1]), "payload": json.loads(str(r[2])), "related_incident_id": None if r[3] is None else int(r[3]), "related_approval_id": None if r[4] is None else str(r[4]), "related_drill_kind": None if r[5] is None else str(r[5]), "created_at_epoch_s": int(r[6])} for r in rows]

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS governance_journal (journal_id INTEGER PRIMARY KEY AUTOINCREMENT, event_kind TEXT NOT NULL, entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL, payload_json TEXT NOT NULL, related_incident_id INTEGER NULL, related_approval_id TEXT NULL, related_drill_kind TEXT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_governance_journal_entity ON governance_journal(entity_kind, entity_id, journal_id DESC)")
            conn.commit()


class SQLiteSimpleAuditEventStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> int:
        now = int(time.time())
        with _connect(self._db_path) as conn:
            cursor = conn.execute("INSERT INTO security_audit_events(event_kind, payload_json, created_at_epoch_s) VALUES(?, ?, ?)", (str(event_kind), json.dumps(dict(payload), ensure_ascii=False), now))
            conn.commit()
            return int(cursor.lastrowid)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT event_kind, payload_json, created_at_epoch_s FROM security_audit_events ORDER BY event_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"event_kind": str(r[0]), "payload": json.loads(str(r[1])), "created_at_epoch_s": int(r[2])} for r in rows]

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_audit_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()


class SQLiteSecurityAuditChainBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        now = int(time.time())
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT event_hash FROM security_audit_chain ORDER BY event_id DESC LIMIT 1").fetchone()
            previous_hash = str(row[0]) if row else "GENESIS"
            event_hash = hashlib.sha256(f"{previous_hash}|{event_kind}|{payload_json}|{now}".encode("utf-8")).hexdigest()
            cursor = conn.execute("INSERT INTO security_audit_chain(event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s) VALUES(?, ?, ?, ?, ?)", (str(event_kind), payload_json, previous_hash, event_hash, now))
            conn.commit()
            return {"event_id": int(cursor.lastrowid), "previous_hash": previous_hash, "event_hash": event_hash, "created_at_epoch_s": now}

    def verify_chain(self) -> dict[str, Any]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT event_id, event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s FROM security_audit_chain ORDER BY event_id ASC").fetchall()
        expected_previous = "GENESIS"
        violations: list[str] = []
        for r in rows:
            event_id = int(r[0]); event_kind = str(r[1]); payload_json = str(r[2]); previous_hash = str(r[3]); event_hash = str(r[4]); created_at_epoch_s = int(r[5])
            if previous_hash != expected_previous:
                violations.append(f"chain_break:{event_id}")
            if hashlib.sha256(f"{previous_hash}|{event_kind}|{payload_json}|{created_at_epoch_s}".encode("utf-8")).hexdigest() != event_hash:
                violations.append(f"hash_mismatch:{event_id}")
            expected_previous = event_hash
        return {"ok": not violations, "violations": violations, "events_checked": len(rows)}

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_audit_chain (event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_kind TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()


class SQLiteTokenRevocationStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def revoke(self, *, token_fingerprint: str, reason: str) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO token_revocations(token_fingerprint, reason, revoked_at_epoch_s) VALUES(?, ?, ?)", (str(token_fingerprint), str(reason), int(time.time()))); conn.commit()
    def is_revoked(self, *, token_fingerprint: str) -> bool:
        with _connect(self._db_path) as conn:
            return conn.execute("SELECT token_fingerprint FROM token_revocations WHERE token_fingerprint = ?", (str(token_fingerprint),)).fetchone() is not None
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS token_revocations (token_fingerprint TEXT PRIMARY KEY, reason TEXT NOT NULL, revoked_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteSecurityDrillScheduleStoreBackend:
    def __init__(self, db_path: str, schedule_cls: type) -> None:
        self._db_path = str(db_path); self._schedule_cls = schedule_cls; self.ensure_schema()
    def put(self, schedule: Any) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("""INSERT OR REPLACE INTO security_drill_schedule(drill_id, drill_kind, actor, target_entity_id, interval_seconds, next_run_epoch_s, enabled, failure_escalation_kind, payload_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""", (str(schedule.drill_id), str(schedule.drill_kind), str(schedule.actor), str(schedule.target_entity_id), int(schedule.interval_seconds), int(schedule.next_run_epoch_s), 1 if schedule.enabled else 0, str(schedule.failure_escalation_kind), json.dumps(dict(schedule.payload or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":")))); conn.commit()
    def _row(self, r: tuple[Any, ...]) -> Any:
        return self._schedule_cls(drill_id=str(r[0]), drill_kind=str(r[1]), actor=str(r[2]), target_entity_id=str(r[3]), interval_seconds=int(r[4]), next_run_epoch_s=int(r[5]), enabled=bool(int(r[6])), failure_escalation_kind=str(r[7]), payload=json.loads(str(r[8] or "{}")))
    def due(self, *, now_epoch_s: int | None = None, limit: int = 50) -> list[Any]:
        now = int(time.time()) if now_epoch_s is None else int(now_epoch_s)
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds, next_run_epoch_s, enabled, failure_escalation_kind, payload_json FROM security_drill_schedule WHERE enabled = 1 AND next_run_epoch_s <= ? ORDER BY next_run_epoch_s ASC, drill_id ASC LIMIT ?", (now, max(int(limit), 1))).fetchall()
        return [self._row(tuple(r)) for r in rows]
    def list_enabled(self) -> list[Any]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds, next_run_epoch_s, enabled, failure_escalation_kind, payload_json FROM security_drill_schedule WHERE enabled = 1 ORDER BY drill_id ASC").fetchall()
        return [self._row(tuple(r)) for r in rows]
    def get_by_drill_id(self, *, drill_id: str) -> Any:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds, next_run_epoch_s, enabled, failure_escalation_kind, payload_json FROM security_drill_schedule WHERE drill_id = ?", (str(drill_id),)).fetchone()
        if row is None:
            raise KeyError(f"unknown drill schedule: {drill_id}")
        return self._row(tuple(row))
    def mark_run(self, *, drill_id: str, next_run_epoch_s: int) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("UPDATE security_drill_schedule SET next_run_epoch_s = ? WHERE drill_id = ?", (int(next_run_epoch_s), str(drill_id))); conn.commit()
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_drill_schedule (drill_id TEXT PRIMARY KEY, drill_kind TEXT NOT NULL, actor TEXT NOT NULL, target_entity_id TEXT NOT NULL, interval_seconds INTEGER NOT NULL, next_run_epoch_s INTEGER NOT NULL, enabled INTEGER NOT NULL, failure_escalation_kind TEXT NOT NULL, payload_json TEXT NOT NULL)"""); conn.commit()


class SQLiteKMSProviderBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def create_key_row(self, *, key_id: str, algorithm: str, exportable: bool) -> int:
        version = self.next_version(key_id=key_id); now = int(time.time())
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO kms_provider_keys(key_id, key_version, algorithm, exportable, created_at_epoch_s, active) VALUES(?, ?, ?, ?, ?, 1)", (str(key_id), version, str(algorithm), 1 if exportable else 0, now))
            conn.execute("UPDATE kms_provider_keys SET active = 0 WHERE key_id = ? AND key_version != ?", (str(key_id), version)); conn.commit()
        return version
    def get_active_key_row(self, *, key_id: str) -> tuple[int, str, bool] | None:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT key_version, algorithm, exportable FROM kms_provider_keys WHERE key_id = ? AND active = 1 ORDER BY key_version DESC LIMIT 1", (str(key_id),)).fetchone()
        return None if row is None else (int(row[0]), str(row[1]), bool(int(row[2])))
    def next_version(self, *, key_id: str) -> int:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT MAX(key_version) FROM kms_provider_keys WHERE key_id = ?", (str(key_id),)).fetchone()
        return (int(row[0]) if row and row[0] is not None else 0) + 1
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS kms_provider_keys (key_id TEXT NOT NULL, key_version INTEGER NOT NULL, algorithm TEXT NOT NULL, exportable INTEGER NOT NULL, created_at_epoch_s INTEGER NOT NULL, active INTEGER NOT NULL, PRIMARY KEY(key_id, key_version))""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kms_provider_keys_lookup ON kms_provider_keys(key_id, active, key_version)"); conn.commit()


class SQLiteReencryptionProgressLedgerBackend:
    def __init__(self, db_path: str, event_cls: type) -> None:
        self._db_path = str(db_path); self._event_cls = event_cls; self.ensure_schema()
    def append(self, event: Any) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO security_reencryption_progress(job_id, event_kind, secret_ref, ok, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)", (event.job_id, event.event_kind, event.secret_ref, 1 if event.ok else 0, json.dumps(event.payload, ensure_ascii=False, sort_keys=True), int(time.time()))); conn.commit()
    def latest_for_job(self, job_id: str, *, limit: int = 100) -> tuple[Any, ...]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT job_id, event_kind, secret_ref, ok, payload_json FROM security_reencryption_progress WHERE job_id = ? ORDER BY rowid DESC LIMIT ?", (str(job_id), int(limit))).fetchall()
        return tuple(self._event_cls(job_id=str(r[0]), event_kind=str(r[1]), secret_ref=r[2], ok=bool(int(r[3])), payload=dict(json.loads(str(r[4] or "{}")))) for r in rows)
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_reencryption_progress (job_id TEXT NOT NULL, event_kind TEXT NOT NULL, secret_ref TEXT NULL, ok INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteKeyRotationJournalBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def append(self, *, key_id: str, old_status: str, new_status: str, payload: Mapping[str, Any]) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO key_rotation_journal(key_id, old_status, new_status, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?)", (str(key_id), str(old_status), str(new_status), json.dumps(dict(payload), ensure_ascii=False), int(time.time()))); conn.commit()
    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT key_id, old_status, new_status, payload_json, created_at_epoch_s FROM key_rotation_journal ORDER BY journal_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"key_id": str(r[0]), "old_status": str(r[1]), "new_status": str(r[2]), "payload": json.loads(str(r[3])), "created_at_epoch_s": int(r[4])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS key_rotation_journal (journal_id INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL, old_status TEXT NOT NULL, new_status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteSecurityIncidentRegistryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def open_incident(self, *, incident_kind: str, payload: Mapping[str, Any]) -> int:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("INSERT INTO security_incidents(incident_kind, status, payload_json, created_at_epoch_s, resolved_at_epoch_s) VALUES(?, 'open', ?, ?, NULL)", (str(incident_kind), json.dumps(dict(payload), ensure_ascii=False), int(time.time()))); conn.commit(); return int(cursor.lastrowid)
    def resolve(self, *, incident_id: int, resolution_payload: Mapping[str, Any] | None = None) -> bool:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("UPDATE security_incidents SET status = 'resolved', resolution_payload_json = ?, resolved_at_epoch_s = ? WHERE incident_id = ? AND status = 'open'", (json.dumps(dict(resolution_payload or {}), ensure_ascii=False), int(time.time()), int(incident_id))); conn.commit(); return int(cursor.rowcount) > 0
    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT incident_id, incident_kind, status, payload_json, resolution_payload_json, created_at_epoch_s, resolved_at_epoch_s FROM security_incidents ORDER BY incident_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"incident_id": int(r[0]), "incident_kind": str(r[1]), "status": str(r[2]), "payload": json.loads(str(r[3])), "resolution_payload": json.loads(str(r[4] or "{}")), "created_at_epoch_s": int(r[5]), "resolved_at_epoch_s": None if r[6] is None else int(r[6])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_incidents (incident_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_kind TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, resolution_payload_json TEXT NULL, created_at_epoch_s INTEGER NOT NULL, resolved_at_epoch_s INTEGER NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_incidents_status_created ON security_incidents(status, created_at_epoch_s)"); conn.commit()


class SQLiteApprovalReplayGuardBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def consume(self, *, approval_id: str, operation_kind: str, actor: str) -> bool:
        with _connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?", (str(approval_id),)).fetchone() is not None:
                conn.rollback(); return False
            conn.execute("INSERT INTO consumed_operator_approvals(approval_id, operation_kind, actor, consumed_at_epoch_s) VALUES(?, ?, ?, ?)", (str(approval_id), str(operation_kind), str(actor), int(time.time()))); conn.commit(); return True
    def has_been_consumed(self, *, approval_id: str) -> bool:
        with _connect(self._db_path) as conn:
            return conn.execute("SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?", (str(approval_id),)).fetchone() is not None
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS consumed_operator_approvals (approval_id TEXT PRIMARY KEY, operation_kind TEXT NOT NULL, actor TEXT NOT NULL, consumed_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteSecurityQuarantineRegistryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def quarantine(self, *, entity_kind: str, entity_id: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO security_quarantine(entity_kind, entity_id, reason, payload_json, quarantined_at_epoch_s, released_at_epoch_s) VALUES(?, ?, ?, ?, ?, NULL)", (str(entity_kind), str(entity_id), str(reason), json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time()))); conn.commit()
    def release(self, *, entity_kind: str, entity_id: str) -> bool:
        with _connect(self._db_path) as conn:
            cursor = conn.execute("UPDATE security_quarantine SET released_at_epoch_s = ? WHERE entity_kind = ? AND entity_id = ? AND released_at_epoch_s IS NULL", (int(time.time()), str(entity_kind), str(entity_id))); conn.commit(); return int(cursor.rowcount) > 0
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_quarantine_active ON security_quarantine(entity_kind, released_at_epoch_s)"); conn.commit()


class SQLiteReencryptionJobStoreBackend:
    def __init__(self, db_path: str, job_cls: type) -> None:
        self._db_path = str(db_path); self._job_cls = job_cls; self.ensure_schema()
    def put(self, job: Any) -> Any:
        with _connect(self._db_path) as conn:
            conn.execute("""INSERT INTO security_reencryption_jobs(job_id, old_key_id, new_key_id, tenant_id, connector_id, status, cursor_secret_ref, processed_count, failed_count, metadata_json, updated_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET old_key_id=excluded.old_key_id, new_key_id=excluded.new_key_id, tenant_id=excluded.tenant_id, connector_id=excluded.connector_id, status=excluded.status, cursor_secret_ref=excluded.cursor_secret_ref, processed_count=excluded.processed_count, failed_count=excluded.failed_count, metadata_json=excluded.metadata_json, updated_at_epoch_s=excluded.updated_at_epoch_s""", (job.job_id, job.old_key_id, job.new_key_id, job.tenant_id, job.connector_id, job.status, job.cursor_secret_ref, int(job.processed_count), int(job.failed_count), json.dumps(job.metadata or {}, ensure_ascii=False, sort_keys=True), int(time.time()))); conn.commit()
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
            conn.execute("""CREATE TABLE IF NOT EXISTS security_reencryption_jobs (job_id TEXT PRIMARY KEY, old_key_id TEXT NOT NULL, new_key_id TEXT NOT NULL, tenant_id TEXT NULL, connector_id TEXT NULL, status TEXT NOT NULL, cursor_secret_ref TEXT NULL, processed_count INTEGER NOT NULL, failed_count INTEGER NOT NULL, metadata_json TEXT NOT NULL, updated_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteSecurityIncidentDrillHistoryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def append(self, *, drill_kind: str, ok: bool, payload: Mapping[str, Any] | None = None) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO security_incident_drill_history(drill_kind, ok, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?)", (str(drill_kind), 1 if ok else 0, json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time()))); conn.commit()
    def latest(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT drill_kind, ok, payload_json, created_at_epoch_s FROM security_incident_drill_history ORDER BY drill_id DESC LIMIT ?", (max(int(limit), 1),)).fetchall()
        return [{"drill_kind": str(r[0]), "ok": bool(int(r[1])), "payload": json.loads(str(r[2])), "created_at_epoch_s": int(r[3])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_incident_drill_history (drill_id INTEGER PRIMARY KEY AUTOINCREMENT, drill_kind TEXT NOT NULL, ok INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SignedOperatorApprovalStoreBackend:
    def __init__(self, db_path: str, shared_secret: str) -> None:
        self._db_path = str(db_path); self._secret = str(shared_secret).encode("utf-8"); self.ensure_schema()
    def _sign(self, *, approval_id: str, operation_kind: str, actor: str, payload_json: str, created_at_epoch_s: int) -> str:
        return hmac.new(self._secret, "|".join([approval_id, operation_kind, actor, payload_json, str(created_at_epoch_s)]).encode("utf-8"), hashlib.sha256).hexdigest()
    def grant(self, *, approval_id: str, operation_kind: str, actor: str, payload: Mapping[str, Any]) -> None:
        now = int(time.time()); payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")); signature = self._sign(approval_id=approval_id, operation_kind=operation_kind, actor=actor, payload_json=payload_json, created_at_epoch_s=now)
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO signed_operator_approvals(approval_id, operation_kind, actor, payload_json, signature, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)", (str(approval_id), str(operation_kind), str(actor), payload_json, signature, now)); conn.commit()
    def verify(self, *, approval_id: str) -> dict[str, Any]:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT operation_kind, actor, payload_json, signature, created_at_epoch_s FROM signed_operator_approvals WHERE approval_id = ?", (str(approval_id),)).fetchone()
        if row is None:
            return {"ok": False, "reason": "approval not found"}
        expected = self._sign(approval_id=str(approval_id), operation_kind=str(row[0]), actor=str(row[1]), payload_json=str(row[2]), created_at_epoch_s=int(row[4]))
        return {"ok": hmac.compare_digest(expected, str(row[3])), "operation_kind": str(row[0]), "actor": str(row[1]), "payload": json.loads(str(row[2])), "created_at_epoch_s": int(row[4])}
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS signed_operator_approvals (approval_id TEXT PRIMARY KEY, operation_kind TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, signature TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)"""); conn.commit()


class SQLiteSecurityOperatorWorkflowStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path); self.ensure_schema()
    def append_step(self, *, workflow_id: str, operation_kind: str, actor: str, step_kind: str, payload: Mapping[str, Any] | None = None) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO security_operator_workflow(workflow_id, operation_kind, actor, step_kind, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)", (str(workflow_id), str(operation_kind), str(actor), str(step_kind), json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time()))); conn.commit()
    def list_steps(self, *, workflow_id: str) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT operation_kind, actor, step_kind, payload_json, created_at_epoch_s FROM security_operator_workflow WHERE workflow_id = ? ORDER BY step_id ASC", (str(workflow_id),)).fetchall()
        return [{"operation_kind": str(r[0]), "actor": str(r[1]), "step_kind": str(r[2]), "payload": json.loads(str(r[3])), "created_at_epoch_s": int(r[4])} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_operator_workflow (step_id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT NOT NULL, operation_kind TEXT NOT NULL, actor TEXT NOT NULL, step_kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_security_operator_workflow_lookup ON security_operator_workflow(workflow_id, created_at_epoch_s)"); conn.commit()


__all__ = [name for name in globals() if name.startswith("SQLite") or name.endswith("Backend") or name == "CANON_PLATFORM_SECURITY_SQLITE_STORES"]
