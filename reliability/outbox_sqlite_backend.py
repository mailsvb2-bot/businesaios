from __future__ import annotations

import importlib
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
sqlite3 = importlib.import_module("sqlite3")
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from core.tenancy.normalization import require_tenant_id
from reliability.outbox_backend import (
    CANON_OUTBOX_BACKEND,
    OutboxBackend,
    OutboxBackendHealth,
    OutboxBackendInspector,
    OutboxBackendMode,
    OutboxDeliveryConflict,
    OutboxDeliveryReceipt,
    OutboxDeliveryRecord,
    OutboxDeliveryStatus,
    utc_now,
)
from reliability.outbox_store import OutboxMessage, canonical_payload_digest


CANON_OUTBOX_SQLITE_BACKEND = True


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported json value: {type(value)!r}")


def _canonical_payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=_json_default, separators=(",", ":"))


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_payload_json(payload).encode("utf-8")).hexdigest()


class SQLiteOutboxBackend(OutboxBackend, OutboxBackendInspector):
    backend_name = "sqlite_outbox_backend"

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def healthcheck(self) -> OutboxBackendHealth:
        health = OutboxBackendHealth(
            backend_name=self.backend_name,
            healthy=self._db_path.exists() or self._db_path.parent.exists(),
            mode=OutboxBackendMode.DURABLE,
            detail=str(self._db_path),
        )
        health.validate()
        return health

    def deliver(self, message: OutboxMessage) -> OutboxDeliveryReceipt:
        message.validate()
        tenant_id = require_tenant_id(message.tenant_id)
        delivered_at = utc_now()
        payload_json = _canonical_payload_json(message.payload)
        payload_digest = message.resolved_payload_digest or canonical_payload_digest(message.payload)
        metadata = {
            "topic": message.topic,
            "dedupe_key": message.dedupe_key,
            "trace_id": message.trace_id,
            "run_id": message.run_id,
            "decision_id": message.decision_id,
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        external_id = f"{tenant_id}:{message.topic}:{message.message_id}"

        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            by_identity = conn.execute(
                """
                SELECT tenant_id, message_id, topic, dedupe_key, payload_json, payload_digest,
                       delivered_at, external_id, backend_name, metadata_json
                FROM outbox_delivery
                WHERE tenant_id = ? AND message_id = ?
                """,
                (tenant_id, message.message_id),
            ).fetchone()
            if by_identity is not None:
                existing = self._row_to_record(by_identity)
                self._assert_semantic_match_or_raise(existing=existing, message=message, incoming_digest=payload_digest)
                conn.commit()
                receipt = OutboxDeliveryReceipt(
                    tenant_id=tenant_id,
                    message_id=message.message_id,
                    backend_name=self.backend_name,
                    status=OutboxDeliveryStatus.DUPLICATE,
                    delivered_at=existing.receipt.delivered_at,
                    external_id=existing.receipt.external_id,
                    payload_digest=existing.receipt.payload_digest,
                    metadata=existing.receipt.metadata,
                )
                receipt.validate()
                return receipt

            by_dedupe = conn.execute(
                """
                SELECT tenant_id, message_id, topic, dedupe_key, payload_json, payload_digest,
                       delivered_at, external_id, backend_name, metadata_json
                FROM outbox_delivery
                WHERE tenant_id = ? AND dedupe_key = ?
                """,
                (tenant_id, message.dedupe_key),
            ).fetchone()
            if by_dedupe is not None:
                existing = self._row_to_record(by_dedupe)
                self._assert_semantic_match_or_raise(existing=existing, message=message, incoming_digest=payload_digest)
                conn.commit()
                receipt = OutboxDeliveryReceipt(
                    tenant_id=tenant_id,
                    message_id=message.message_id,
                    backend_name=self.backend_name,
                    status=OutboxDeliveryStatus.DUPLICATE,
                    delivered_at=existing.receipt.delivered_at,
                    external_id=existing.receipt.external_id,
                    payload_digest=existing.receipt.payload_digest,
                    metadata=existing.receipt.metadata,
                )
                receipt.validate()
                return receipt

            conn.execute(
                """
                INSERT INTO outbox_delivery (
                    tenant_id,
                    message_id,
                    topic,
                    dedupe_key,
                    payload_json,
                    payload_digest,
                    delivered_at,
                    external_id,
                    backend_name,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    message.message_id,
                    message.topic,
                    message.dedupe_key,
                    payload_json,
                    payload_digest,
                    delivered_at.isoformat(),
                    external_id,
                    self.backend_name,
                    metadata_json,
                ),
            )
            conn.commit()

        receipt = OutboxDeliveryReceipt(
            tenant_id=tenant_id,
            message_id=message.message_id,
            backend_name=self.backend_name,
            status=OutboxDeliveryStatus.DELIVERED,
            delivered_at=delivered_at,
            external_id=external_id,
            payload_digest=payload_digest,
            metadata=metadata,
        )
        receipt.validate()
        return receipt

    def get_receipt(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryReceipt | None:
        record = self.get_record(tenant_id=tenant_id, message_id=message_id)
        return None if record is None else record.receipt

    def get_record(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryRecord | None:
        tid = require_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, message_id, topic, dedupe_key, payload_json, payload_digest,
                       delivered_at, external_id, backend_name, metadata_json
                FROM outbox_delivery
                WHERE tenant_id = ? AND message_id = ?
                """,
                (tid, str(message_id)),
            ).fetchone()
        return None if row is None else self._row_to_record(row)

    def list_records(
        self,
        *,
        tenant_id: str,
        topic: str | None = None,
        limit: int = 100,
    ) -> tuple[OutboxDeliveryRecord, ...]:
        tid = require_tenant_id(tenant_id)
        query = (
            "SELECT tenant_id, message_id, topic, dedupe_key, payload_json, payload_digest, "
            "delivered_at, external_id, backend_name, metadata_json "
            "FROM outbox_delivery WHERE tenant_id = ?"
        )
        params: list[Any] = [tid]
        if topic is not None:
            query += " AND topic = ?"
            params.append(str(topic))
        query += " ORDER BY delivered_at ASC, message_id ASC LIMIT ?"
        max_items = max(0, int(limit))
        if max_items == 0:
            return ()
        params.append(max_items)

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox_delivery (
                    tenant_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT,
                    delivered_at TEXT NOT NULL,
                    external_id TEXT,
                    backend_name TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, message_id)
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_outbox_delivery_tenant_dedupe
                ON outbox_delivery (tenant_id, dedupe_key)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_outbox_delivery_tenant_topic_time
                ON outbox_delivery (tenant_id, topic, delivered_at)
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _assert_semantic_match_or_raise(
        *,
        existing: OutboxDeliveryRecord,
        message: OutboxMessage,
        incoming_digest: str,
    ) -> None:
        existing_digest = str(existing.receipt.payload_digest or "").strip()
        if existing.topic != message.topic:
            raise OutboxDeliveryConflict(
                "sqlite outbox backend detected topic drift for deduped delivery",
                details={
                    "tenant_id": message.tenant_id,
                    "message_id": message.message_id,
                    "existing_topic": existing.topic,
                    "incoming_topic": message.topic,
                },
            )
        if existing_digest and existing_digest != incoming_digest:
            raise OutboxDeliveryConflict(
                "sqlite outbox backend detected payload drift for existing delivery identity",
                details={
                    "tenant_id": message.tenant_id,
                    "message_id": message.message_id,
                    "existing_digest": existing_digest,
                    "incoming_digest": incoming_digest,
                },
            )

    @staticmethod
    def _row_to_record(row: sqlite3.Row | tuple[Any, ...]) -> OutboxDeliveryRecord:
        if not isinstance(row, sqlite3.Row):
            (
                tenant_id,
                message_id,
                topic,
                dedupe_key,
                payload_json,
                payload_digest,
                delivered_at,
                external_id,
                backend_name,
                metadata_json,
            ) = row
        else:
            tenant_id = row["tenant_id"]
            message_id = row["message_id"]
            topic = row["topic"]
            dedupe_key = row["dedupe_key"]
            payload_json = row["payload_json"]
            payload_digest = row["payload_digest"]
            delivered_at = row["delivered_at"]
            external_id = row["external_id"]
            backend_name = row["backend_name"]
            metadata_json = row["metadata_json"]

        receipt = OutboxDeliveryReceipt(
            tenant_id=str(tenant_id),
            message_id=str(message_id),
            backend_name=str(backend_name),
            status=OutboxDeliveryStatus.DELIVERED,
            delivered_at=datetime.fromisoformat(str(delivered_at)),
            external_id=None if external_id is None else str(external_id),
            payload_digest=None if payload_digest is None else str(payload_digest),
            metadata=json.loads(metadata_json or "{}"),
        )
        record = OutboxDeliveryRecord(
            receipt=receipt,
            topic=str(topic),
            dedupe_key=str(dedupe_key),
            payload=json.loads(payload_json or "{}"),
        )
        record.validate()
        return record


__all__ = [
    "CANON_OUTBOX_BACKEND",
    "CANON_OUTBOX_SQLITE_BACKEND",
    "SQLiteOutboxBackend",
]
