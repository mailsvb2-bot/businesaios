from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime.platform.security_sqlite_backends.common import _connect, _ensure_parent

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
            event_hash = hashlib.sha256(f"{previous_hash}|{event_kind}|{payload_json}|{now}".encode()).hexdigest()
            cursor = conn.execute("INSERT INTO security_audit_chain(event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s) VALUES(?, ?, ?, ?, ?)", (str(event_kind), payload_json, previous_hash, event_hash, now))
            conn.commit()
            return {"event_id": int(cursor.lastrowid), "previous_hash": previous_hash, "event_hash": event_hash, "created_at_epoch_s": now}

    def verify_chain(self) -> dict[str, Any]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT event_id, event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s FROM security_audit_chain ORDER BY event_id ASC").fetchall()
        expected_previous = "GENESIS"
        violations: list[str] = []
        for r in rows:
            event_id = int(r[0])
            event_kind = str(r[1])
            payload_json = str(r[2])
            previous_hash = str(r[3])
            event_hash = str(r[4])
            created_at_epoch_s = int(r[5])
            if previous_hash != expected_previous:
                violations.append(f"chain_break:{event_id}")
            if hashlib.sha256(f"{previous_hash}|{event_kind}|{payload_json}|{created_at_epoch_s}".encode()).hexdigest() != event_hash:
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
        self._db_path = str(db_path)
        self.ensure_schema()
    def revoke(self, *, token_fingerprint: str, reason: str) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO token_revocations(token_fingerprint, reason, revoked_at_epoch_s) VALUES(?, ?, ?)", (str(token_fingerprint), str(reason), int(time.time())))
            conn.commit()
    def is_revoked(self, *, token_fingerprint: str) -> bool:
        with _connect(self._db_path) as conn:
            return conn.execute("SELECT token_fingerprint FROM token_revocations WHERE token_fingerprint = ?", (str(token_fingerprint),)).fetchone() is not None
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS token_revocations (token_fingerprint TEXT PRIMARY KEY, reason TEXT NOT NULL, revoked_at_epoch_s INTEGER NOT NULL)""")
            conn.commit()

class SQLiteSecurityDrillScheduleStoreBackend:
    def __init__(self, db_path: str, schedule_cls: type) -> None:
        self._db_path = str(db_path)
        self._schedule_cls = schedule_cls
        self.ensure_schema()
    def put(self, schedule: Any) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("""INSERT OR REPLACE INTO security_drill_schedule(drill_id, drill_kind, actor, target_entity_id, interval_seconds, next_run_epoch_s, enabled, failure_escalation_kind, payload_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""", (str(schedule.drill_id), str(schedule.drill_kind), str(schedule.actor), str(schedule.target_entity_id), int(schedule.interval_seconds), int(schedule.next_run_epoch_s), 1 if schedule.enabled else 0, str(schedule.failure_escalation_kind), json.dumps(dict(schedule.payload or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
            conn.commit()
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
            conn.execute("UPDATE security_drill_schedule SET next_run_epoch_s = ? WHERE drill_id = ?", (int(next_run_epoch_s), str(drill_id)))
            conn.commit()
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS security_drill_schedule (drill_id TEXT PRIMARY KEY, drill_kind TEXT NOT NULL, actor TEXT NOT NULL, target_entity_id TEXT NOT NULL, interval_seconds INTEGER NOT NULL, next_run_epoch_s INTEGER NOT NULL, enabled INTEGER NOT NULL, failure_escalation_kind TEXT NOT NULL, payload_json TEXT NOT NULL)""")
            conn.commit()

class SQLiteKMSProviderBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def create_key_row(self, *, key_id: str, algorithm: str, exportable: bool) -> int:
        version = self.next_version(key_id=key_id)
        now = int(time.time())
        with _connect(self._db_path) as conn:
            conn.execute("INSERT INTO kms_provider_keys(key_id, key_version, algorithm, exportable, created_at_epoch_s, active) VALUES(?, ?, ?, ?, ?, 1)", (str(key_id), version, str(algorithm), 1 if exportable else 0, now))
            conn.execute("UPDATE kms_provider_keys SET active = 0 WHERE key_id = ? AND key_version != ?", (str(key_id), version))
            conn.commit()
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kms_provider_keys_lookup ON kms_provider_keys(key_id, active, key_version)")
            conn.commit()

__all__ = [
    "SQLiteGovernanceJournalStore",
    "SQLiteSimpleAuditEventStoreBackend",
    "SQLiteSecurityAuditChainBackend",
    "SQLiteTokenRevocationStoreBackend",
    "SQLiteSecurityDrillScheduleStoreBackend",
    "SQLiteKMSProviderBackend",
]
