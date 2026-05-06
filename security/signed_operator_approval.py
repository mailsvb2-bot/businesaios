from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SIGNED_OPERATOR_APPROVAL = True


class SignedOperatorApprovalStore:
    """Durable signed approvals for high-risk security operations."""

    def __init__(self, db_path: str, shared_secret: str) -> None:
        self._db_path = str(db_path)
        self._secret = str(shared_secret).encode('utf-8')
        self._ensure_schema()

    def grant(
        self,
        *,
        approval_id: str,
        operation_kind: str,
        actor: str,
        payload: Mapping[str, Any],
    ) -> None:
        now = int(time.time())
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        signature = self._sign(
            approval_id=approval_id,
            operation_kind=operation_kind,
            actor=actor,
            payload_json=payload_json,
            created_at_epoch_s=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO signed_operator_approvals(
                    approval_id, operation_kind, actor, payload_json, signature, created_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (str(approval_id), str(operation_kind), str(actor), payload_json, signature, now),
            )
            conn.commit()

    def verify(self, *, approval_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT operation_kind, actor, payload_json, signature, created_at_epoch_s FROM signed_operator_approvals WHERE approval_id = ?",
                (str(approval_id),),
            ).fetchone()
        if row is None:
            return {'ok': False, 'reason': 'approval not found'}
        operation_kind = str(row[0])
        actor = str(row[1])
        payload_json = str(row[2])
        signature = str(row[3])
        created_at_epoch_s = int(row[4])
        expected = self._sign(
            approval_id=str(approval_id),
            operation_kind=operation_kind,
            actor=actor,
            payload_json=payload_json,
            created_at_epoch_s=created_at_epoch_s,
        )
        return {
            'ok': hmac.compare_digest(expected, signature),
            'operation_kind': operation_kind,
            'actor': actor,
            'payload': json.loads(payload_json),
            'created_at_epoch_s': created_at_epoch_s,
        }

    def _sign(self, *, approval_id: str, operation_kind: str, actor: str, payload_json: str, created_at_epoch_s: int) -> str:
        body = '|'.join([approval_id, operation_kind, actor, payload_json, str(created_at_epoch_s)])
        return hmac.new(self._secret, body.encode('utf-8'), hashlib.sha256).hexdigest()

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signed_operator_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SIGNED_OPERATOR_APPROVAL',
    'SignedOperatorApprovalStore',
]
