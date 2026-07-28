from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


CANON_WEBHOOK_REPLAY_STORE = True


@dataclass(frozen=True)
class WebhookReplayClaim:
    tenant_id: str
    connector_id: str
    nonce: str
    signature_timestamp: str
    content_digest: str


class SQLiteWebhookReplayStore:
    """Persistent atomic replay registry shared by all local API workers."""

    def __init__(self, path: str | Path, *, retention_seconds: int = 86400) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._retention_seconds = max(600, int(retention_seconds))
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def claim(self, claim: WebhookReplayClaim, *, now: datetime | None = None) -> bool:
        tenant_id = str(claim.tenant_id or "").strip()
        connector_id = str(claim.connector_id or "").strip()
        nonce = str(claim.nonce or "").strip()
        if not tenant_id or not connector_id or not nonce:
            raise ValueError("tenant_id, connector_id and nonce are required")
        moment = now or datetime.now(UTC)
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        claimed_at = moment.astimezone(UTC).isoformat()

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM webhook_replay_claims WHERE claimed_at_utc < ?",
                ((moment - timedelta(seconds=self._retention_seconds)).astimezone(UTC).isoformat(),),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO webhook_replay_claims (
                        tenant_id,
                        connector_id,
                        nonce,
                        signature_timestamp,
                        content_digest,
                        claimed_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        connector_id,
                        nonce,
                        str(claim.signature_timestamp),
                        str(claim.content_digest),
                        claimed_at,
                    ),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                return False
            connection.commit()
            return True
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30.0, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_replay_claims (
                    tenant_id TEXT NOT NULL,
                    connector_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    signature_timestamp TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    claimed_at_utc TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, connector_id, nonce)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_webhook_replay_claimed_at ON webhook_replay_claims(claimed_at_utc)"
            )
        finally:
            connection.close()


def webhook_replay_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_WEBHOOK_REPLAY_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_DATA_DIR", os.getenv("DATA_DIR", "data")).strip() or "data"
    return Path(data_dir) / "security" / "webhook_replay.sqlite3"


def build_default_webhook_replay_store() -> SQLiteWebhookReplayStore:
    retention = int(os.getenv("BUSINESAIOS_WEBHOOK_REPLAY_RETENTION_SECONDS", "86400"))
    return SQLiteWebhookReplayStore(webhook_replay_store_path(), retention_seconds=retention)


__all__ = [
    "CANON_WEBHOOK_REPLAY_STORE",
    "SQLiteWebhookReplayStore",
    "WebhookReplayClaim",
    "build_default_webhook_replay_store",
    "webhook_replay_store_path",
]
