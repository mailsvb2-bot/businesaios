from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from runtime.platform.security_sqlite_stores import SQLiteWebhookReplayStoreBackend


CANON_WEBHOOK_REPLAY_STORE = True


@dataclass(frozen=True)
class WebhookReplayClaim:
    tenant_id: str
    connector_id: str
    nonce: str
    signature_timestamp: str
    content_digest: str


class SQLiteWebhookReplayStore:
    """Security-facing replay facade over the runtime-owned atomic backend."""

    def __init__(self, path: str | Path, *, retention_seconds: int = 86400) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._retention_seconds = max(600, int(retention_seconds))
        self._backend = SQLiteWebhookReplayStoreBackend(str(self._path))

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
        normalized = moment.astimezone(UTC)
        return self._backend.claim(
            tenant_id=tenant_id,
            connector_id=connector_id,
            nonce=nonce,
            signature_timestamp=str(claim.signature_timestamp),
            content_digest=str(claim.content_digest),
            claimed_at_utc=normalized.isoformat(),
            expires_before_utc=(normalized - timedelta(seconds=self._retention_seconds)).isoformat(),
        )


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
