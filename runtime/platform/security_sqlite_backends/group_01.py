from __future__ import annotations

import hashlib
import hmac
import json
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
        return {"ok": not violations, "violations": violations}

class SQLiteTokenRevocationStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def revoke(self, *, token_hash: str, reason: str = "") -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO revoked_tokens(token_hash, reason, revoked_at_epoch_s) VALUES(?, ?, ?)", (str(token_hash), str(reason), int(time.time())))
            conn.commit()
    def is_revoked(self, token_hash: str) -> bool:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT 1 FROM revoked_tokens WHERE token_hash = ?", (str(token_hash),)).fetchone()
        return row is not None
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS revoked_tokens(token_hash TEXT PRIMARY KEY, reason TEXT NOT NULL, revoked_at_epoch_s INTEGER NOT NULL)")
            conn.commit()

class SQLiteSecurityDrillScheduleStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()
    def upsert_schedule(self, *, drill_kind: str, cron_expr: str, enabled: bool = True) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO security_drill_schedule(drill_kind, cron_expr, enabled) VALUES(?, ?, ?)", (str(drill_kind), str(cron_expr), 1 if enabled else 0))
            conn.commit()
    def list_schedules(self) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT drill_kind, cron_expr, enabled FROM security_drill_schedule ORDER BY drill_kind").fetchall()
        return [{"drill_kind": str(r[0]), "cron_expr": str(r[1]), "enabled": bool(int(r[2]))} for r in rows]
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS security_drill_schedule(drill_kind TEXT PRIMARY KEY, cron_expr TEXT NOT NULL, enabled INTEGER NOT NULL)")
            conn.commit()

class SQLiteKMSProviderBackend:
    def __init__(self, db_path: str, shared_secret: str) -> None:
        self._db_path = str(db_path)
        self._secret = str(shared_secret).encode("utf-8")
        self.ensure_schema()
    def _sign(self, payload_json: str, nonce: str) -> str:
        return hmac.new(self._secret, f"{payload_json}|{nonce}".encode(), hashlib.sha256).hexdigest()
    def store(self, *, secret_ref: str, payload: Mapping[str, Any], nonce: str) -> str:
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        signature = self._sign(payload_json, nonce)
        with _connect(self._db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO kms_provider(secret_ref, payload_json, nonce, signature, created_at_epoch_s) VALUES(?, ?, ?, ?, ?)", (str(secret_ref), payload_json, str(nonce), signature, int(time.time())))
            conn.commit()
        return signature
    def load(self, secret_ref: str) -> dict[str, Any] | None:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT payload_json, nonce, signature FROM kms_provider WHERE secret_ref = ?", (str(secret_ref),)).fetchone()
        return None if row is None else {"payload": json.loads(str(row[0])), "nonce": str(row[1]), "signature": str(row[2])}
    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS kms_provider(secret_ref TEXT PRIMARY KEY, payload_json TEXT NOT NULL, nonce TEXT NOT NULL, signature TEXT NOT NULL, created_at_epoch_s INTEGER NOT NULL)")
            conn.commit()
