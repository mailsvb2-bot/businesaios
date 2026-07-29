from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.execution.region_ownership_plane import RegionRoute, RegionStatePort


CANON_BUSINESS_AUTONOMY_SQLITE_STATE = True
CANON_PLATFORM_BUSINESS_AUTONOMY_SQLITE_STATE_OWNER = True


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteStateDatabase:
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 30000) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.busy_timeout_ms = max(1000, int(busy_timeout_ms))
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        return connection

    def _initialize(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS distributed_documents (
                    collection TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (collection, document_id)
                );
                CREATE INDEX IF NOT EXISTS idx_distributed_documents_prefix
                    ON distributed_documents(collection, document_id);

                CREATE TABLE IF NOT EXISTS distributed_cas (
                    scope TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    expires_at_epoch REAL NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (scope, record_key)
                );

                CREATE TABLE IF NOT EXISTS distributed_sequences (
                    namespace TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS distributed_evidence (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    partition_key TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_distributed_evidence_partition
                    ON distributed_evidence(partition_key, sequence_id DESC);
                """
            )
        finally:
            connection.close()


class SQLiteDistributedDocumentStore:
    def __init__(self, database: SQLiteStateDatabase, *, collection_prefix: str = "") -> None:
        self.database = database
        self.collection_prefix = str(collection_prefix).strip()

    def _collection(self, collection: str) -> str:
        value = str(collection).strip()
        return f"{self.collection_prefix}:{value}" if self.collection_prefix else value

    def get(self, *, collection: str, document_id: str) -> Mapping[str, Any] | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT version, payload_json, updated_at_utc FROM distributed_documents WHERE collection = ? AND document_id = ?",
                (self._collection(collection), str(document_id).strip()),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        payload = dict(json.loads(str(row["payload_json"])))
        return {
            **payload,
            "version": int(row["version"]),
            "updated_at_utc": str(payload.get("updated_at_utc") or row["updated_at_utc"]),
        }

    def put(
        self,
        *,
        collection: str,
        document_id: str,
        payload: Mapping[str, Any],
        expected_version: int | None = None,
    ) -> int:
        doc_id = str(document_id).strip()
        if not doc_id:
            raise ValueError("document_id is required")
        collection_key = self._collection(collection)
        now = str(payload.get("updated_at_utc") or _utc_now_text())
        stored_payload = {k: v for k, v in dict(payload).items() if k != "version"}
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version FROM distributed_documents WHERE collection = ? AND document_id = ?",
                (collection_key, doc_id),
            ).fetchone()
            current_version = 0 if row is None else int(row["version"])
            if expected_version is not None and current_version != int(expected_version):
                connection.rollback()
                raise ValueError("distributed document version mismatch")
            next_version = current_version + 1
            connection.execute(
                """
                INSERT INTO distributed_documents(collection, document_id, version, payload_json, updated_at_utc)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collection, document_id) DO UPDATE SET
                    version=excluded.version,
                    payload_json=excluded.payload_json,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    collection_key,
                    doc_id,
                    next_version,
                    json.dumps(stored_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    now,
                ),
            )
            connection.commit()
            return next_version
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def list_prefix(self, *, collection: str, prefix: str, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT document_id, version, payload_json, updated_at_utc
                FROM distributed_documents
                WHERE collection = ? AND document_id LIKE ?
                ORDER BY updated_at_utc DESC, document_id ASC
                LIMIT ?
                """,
                (self._collection(collection), f"{str(prefix)}%", max(1, int(limit))),
            ).fetchall()
        finally:
            connection.close()
        return tuple(
            {
                **dict(json.loads(str(row["payload_json"]))),
                "version": int(row["version"]),
                "updated_at_utc": str(row["updated_at_utc"]),
            }
            for row in rows
        )


class SQLiteDistributedCompareAndSwap:
    def __init__(self, database: SQLiteStateDatabase, *, scope: str = "cas") -> None:
        self.database = database
        self.scope = str(scope).strip() or "cas"

    def create_if_absent(self, *, key: str, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool:
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("key is required")
        expires_at = None if ttl_seconds is None else time.time() + max(1, int(ttl_seconds))
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM distributed_cas WHERE scope = ? AND record_key = ? AND expires_at_epoch IS NOT NULL AND expires_at_epoch <= ?",
                (self.scope, normalized_key, time.time()),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO distributed_cas(scope, record_key, version, payload_json, expires_at_epoch, updated_at_utc)
                    VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (
                        self.scope,
                        normalized_key,
                        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        expires_at,
                        _utc_now_text(),
                    ),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                return False
            connection.commit()
            return True
        finally:
            connection.close()

    def read(self, *, key: str) -> Mapping[str, Any] | None:
        normalized_key = str(key).strip()
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, payload_json, expires_at_epoch FROM distributed_cas WHERE scope = ? AND record_key = ?",
                (self.scope, normalized_key),
            ).fetchone()
            if row is not None and row["expires_at_epoch"] is not None and float(row["expires_at_epoch"]) <= time.time():
                connection.execute(
                    "DELETE FROM distributed_cas WHERE scope = ? AND record_key = ?",
                    (self.scope, normalized_key),
                )
                connection.commit()
                return None
            connection.commit()
        finally:
            connection.close()
        if row is None:
            return None
        return {**dict(json.loads(str(row["payload_json"]))), "version": int(row["version"])}

    def compare_and_swap(
        self,
        *,
        key: str,
        expected_version: int,
        payload: Mapping[str, Any],
        ttl_seconds: int | None = None,
    ) -> bool:
        normalized_key = str(key).strip()
        expires_at = None if ttl_seconds is None else time.time() + max(1, int(ttl_seconds))
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE distributed_cas
                SET version = ?, payload_json = ?, expires_at_epoch = ?, updated_at_utc = ?
                WHERE scope = ? AND record_key = ? AND version = ?
                """,
                (
                    int(expected_version) + 1,
                    json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    expires_at,
                    _utc_now_text(),
                    self.scope,
                    normalized_key,
                    int(expected_version),
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.commit()
            return True
        finally:
            connection.close()


class SQLiteDistributedSequenceStore:
    def __init__(self, database: SQLiteStateDatabase) -> None:
        self.database = database

    def next_value(self, *, namespace: str) -> int:
        key = str(namespace).strip()
        if not key:
            raise ValueError("namespace is required")
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                INSERT INTO distributed_sequences(namespace, value)
                VALUES (?, 1)
                ON CONFLICT(namespace) DO UPDATE SET value = value + 1
                RETURNING value
                """,
                (key,),
            ).fetchone()
            connection.commit()
            assert row is not None
            return int(row["value"])
        finally:
            connection.close()


class SQLiteDistributedEvidenceAppendPort:
    def __init__(self, database: SQLiteStateDatabase) -> None:
        self.database = database

    def append(self, *, partition_key: str, payload: Mapping[str, Any]) -> str:
        item_id = str(payload.get("evidence_id") or payload.get("event_id") or uuid4())
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO distributed_evidence(partition_key, item_id, payload_json, created_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(partition_key),
                    item_id,
                    json.dumps({**dict(payload), "_id": item_id}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    _utc_now_text(),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return item_id

    def read_partition(
        self,
        *,
        partition_key: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[Sequence[Mapping[str, Any]], str | None]:
        del cursor
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT payload_json FROM distributed_evidence
                WHERE partition_key = ?
                ORDER BY sequence_id DESC
                LIMIT ?
                """,
                (str(partition_key), max(1, int(limit))),
            ).fetchall()
        finally:
            connection.close()
        return tuple(dict(json.loads(str(row["payload_json"]))) for row in rows), None

    def read_prefix(
        self,
        *,
        prefix: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[Sequence[Mapping[str, Any]], str | None]:
        del cursor
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT payload_json FROM distributed_evidence
                WHERE partition_key LIKE ?
                ORDER BY sequence_id DESC
                LIMIT ?
                """,
                (f"{str(prefix)}%", max(1, int(limit))),
            ).fetchall()
        finally:
            connection.close()
        return tuple(dict(json.loads(str(row["payload_json"]))) for row in rows), None


@dataclass(frozen=True)
class SQLiteRegionRouteState(RegionStatePort):
    database: SQLiteStateDatabase
    collection: str = "region_routes"
    barriers_collection: str = "region_cutover_barriers"

    def _documents(self) -> SQLiteDistributedDocumentStore:
        return SQLiteDistributedDocumentStore(self.database)

    def read_route(self, *, tenant_id: str, business_id: str) -> RegionRoute | None:
        payload = self._documents().get(collection=self.collection, document_id=f"{tenant_id}:{business_id}")
        if payload is None:
            return None
        return RegionRoute(
            tenant_id=str(payload.get("tenant_id") or tenant_id),
            business_id=str(payload.get("business_id") or business_id),
            primary_region=str(payload.get("primary_region") or "global"),
            failover_region=str(payload.get("failover_region") or "global"),
            routing_epoch=int(payload.get("routing_epoch") or 0),
            ownership_token=int(payload.get("ownership_token") or 0),
        )

    def compare_and_swap_route(
        self,
        *,
        tenant_id: str,
        business_id: str,
        expected_epoch: int | None,
        route: RegionRoute,
    ) -> bool:
        document_id = f"{tenant_id}:{business_id}"
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, payload_json FROM distributed_documents WHERE collection = ? AND document_id = ?",
                (self.collection, document_id),
            ).fetchone()
            current_epoch = None
            current_version = 0
            if row is not None:
                current_version = int(row["version"])
                current_epoch = int(dict(json.loads(str(row["payload_json"]))).get("routing_epoch") or 0)
            if current_epoch != expected_epoch:
                connection.rollback()
                return False
            payload = {
                "tenant_id": route.tenant_id,
                "business_id": route.business_id,
                "primary_region": route.primary_region,
                "failover_region": route.failover_region,
                "routing_epoch": route.routing_epoch,
                "ownership_token": route.ownership_token,
                "updated_at_utc": _utc_now_text(),
            }
            connection.execute(
                """
                INSERT INTO distributed_documents(collection, document_id, version, payload_json, updated_at_utc)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collection, document_id) DO UPDATE SET
                    version=excluded.version,
                    payload_json=excluded.payload_json,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    self.collection,
                    document_id,
                    current_version + 1,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    payload["updated_at_utc"],
                ),
            )
            connection.commit()
            return True
        finally:
            connection.close()

    def allocate_cutover_barrier(self, *, tenant_id: str, business_id: str, target_region: str) -> str:
        barrier_id = f"barrier:{tenant_id}:{business_id}:{target_region}:{uuid4()}"
        self._documents().put(
            collection=self.barriers_collection,
            document_id=barrier_id,
            payload={
                "tenant_id": tenant_id,
                "business_id": business_id,
                "target_region": target_region,
                "created_at_utc": _utc_now_text(),
            },
        )
        return barrier_id


__all__ = [
    "CANON_BUSINESS_AUTONOMY_SQLITE_STATE",
    "SQLiteDistributedCompareAndSwap",
    "SQLiteDistributedDocumentStore",
    "SQLiteDistributedEvidenceAppendPort",
    "SQLiteDistributedSequenceStore",
    "SQLiteRegionRouteState",
    "SQLiteStateDatabase",
]
