from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from collections.abc import Mapping
from typing import Any

from runtime.platform.security_sqlite_backends.common import _connect, _ensure_parent


class SQLiteSecurityIncidentDrillHistoryBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def append(self, *, drill_kind: str, ok: bool, payload: Mapping[str, Any] | None = None) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO security_incident_drill_history(drill_kind, ok, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?)",
                (str(drill_kind), 1 if ok else 0, json.dumps(dict(payload or {}), ensure_ascii=False), int(time.time())),
            )
            conn.commit()

    def latest(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT drill_kind, ok, payload_json, created_at_epoch_s FROM security_incident_drill_history ORDER BY drill_id DESC LIMIT ?",
                (max(int(limit), 1),),
            ).fetchall()
        return [
            {
                "drill_kind": str(row[0]),
                "ok": bool(int(row[1])),
                "payload": json.loads(str(row[2])),
                "created_at_epoch_s": int(row[3]),
            }
            for row in rows
        ]

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS security_incident_drill_history (
                    drill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drill_kind TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )"""
            )
            conn.commit()


class SignedOperatorApprovalStoreBackend:
    def __init__(self, db_path: str, shared_secret: str) -> None:
        self._db_path = str(db_path)
        self._secret = str(shared_secret).encode("utf-8")
        self.ensure_schema()

    def _sign(self, *, approval_id: str, operation_kind: str, actor: str, payload_json: str, created_at_epoch_s: int) -> str:
        return hmac.new(
            self._secret,
            "|".join([approval_id, operation_kind, actor, payload_json, str(created_at_epoch_s)]).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def grant(self, *, approval_id: str, operation_kind: str, actor: str, payload: Mapping[str, Any]) -> None:
        now = int(time.time())
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        signature = self._sign(
            approval_id=approval_id,
            operation_kind=operation_kind,
            actor=actor,
            payload_json=payload_json,
            created_at_epoch_s=now,
        )
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO signed_operator_approvals(approval_id, operation_kind, actor, payload_json, signature, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)",
                (str(approval_id), str(operation_kind), str(actor), payload_json, signature, now),
            )
            conn.commit()

    def verify(self, *, approval_id: str) -> dict[str, Any]:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT operation_kind, actor, payload_json, signature, created_at_epoch_s FROM signed_operator_approvals WHERE approval_id = ?",
                (str(approval_id),),
            ).fetchone()
        if row is None:
            return {"ok": False, "reason": "approval not found"}
        expected = self._sign(
            approval_id=str(approval_id),
            operation_kind=str(row[0]),
            actor=str(row[1]),
            payload_json=str(row[2]),
            created_at_epoch_s=int(row[4]),
        )
        return {
            "ok": hmac.compare_digest(expected, str(row[3])),
            "operation_kind": str(row[0]),
            "actor": str(row[1]),
            "payload": json.loads(str(row[2])),
            "created_at_epoch_s": int(row[4]),
        }

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS signed_operator_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )"""
            )
            conn.commit()


class SQLiteSecurityOperatorWorkflowStoreBackend:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def append_step(
        self,
        *,
        workflow_id: str,
        operation_kind: str,
        actor: str,
        step_kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO security_operator_workflow(workflow_id, operation_kind, actor, step_kind, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)",
                (
                    str(workflow_id),
                    str(operation_kind),
                    str(actor),
                    str(step_kind),
                    json.dumps(dict(payload or {}), ensure_ascii=False),
                    int(time.time()),
                ),
            )
            conn.commit()

    def list_steps(self, *, workflow_id: str) -> list[dict[str, Any]]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT operation_kind, actor, step_kind, payload_json, created_at_epoch_s FROM security_operator_workflow WHERE workflow_id = ? ORDER BY step_id ASC",
                (str(workflow_id),),
            ).fetchall()
        return [
            {
                "operation_kind": str(row[0]),
                "actor": str(row[1]),
                "step_kind": str(row[2]),
                "payload": json.loads(str(row[3])),
                "created_at_epoch_s": int(row[4]),
            }
            for row in rows
        ]

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS security_operator_workflow (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    operation_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    step_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_operator_workflow_lookup ON security_operator_workflow(workflow_id, created_at_epoch_s)"
            )
            conn.commit()


class SQLiteWebhookReplayStoreBackend:
    """Runtime-owned atomic nonce claim store for webhook verification."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def claim(
        self,
        *,
        tenant_id: str,
        connector_id: str,
        nonce: str,
        signature_timestamp: str,
        content_digest: str,
        claimed_at_utc: str,
        expires_before_utc: str,
    ) -> bool:
        with _connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM webhook_replay_claims WHERE claimed_at_utc < ?",
                (str(expires_before_utc),),
            )
            try:
                conn.execute(
                    """INSERT INTO webhook_replay_claims (
                        tenant_id,
                        connector_id,
                        nonce,
                        signature_timestamp,
                        content_digest,
                        claimed_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(tenant_id),
                        str(connector_id),
                        str(nonce),
                        str(signature_timestamp),
                        str(content_digest),
                        str(claimed_at_utc),
                    ),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
            conn.commit()
            return True

    def ensure_schema(self) -> None:
        _ensure_parent(self._db_path)
        with _connect(self._db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS webhook_replay_claims (
                    tenant_id TEXT NOT NULL,
                    connector_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    signature_timestamp TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    claimed_at_utc TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, connector_id, nonce)
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_webhook_replay_claimed_at ON webhook_replay_claims(claimed_at_utc)"
            )
            conn.commit()


__all__ = [
    "SQLiteSecurityIncidentDrillHistoryBackend",
    "SignedOperatorApprovalStoreBackend",
    "SQLiteSecurityOperatorWorkflowStoreBackend",
    "SQLiteWebhookReplayStoreBackend",
]
