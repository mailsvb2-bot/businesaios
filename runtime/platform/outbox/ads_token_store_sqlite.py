from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from connectors.platform.ads.token_store import AdsTokenStore, OAuthToken


class SqliteAdsTokenStore(AdsTokenStore):
    """SQLite-backed ads OAuth token store.

    Placed under `runtime/platform/outbox/` to comply with architecture rules that
    restrict raw sqlite3 usage to a small set of platform-layer components.

    This is a pragmatic default for single-node deployments.
    """

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        self._lock = threading.Lock()

    def ensure_schema(self) -> None:
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ads_oauth_tokens (
                    tenant_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    token_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, platform, account_id)
                );
                """
            )
            conn.commit()

    def put(self, *, tenant_id: str, platform: str, account_id: str, token: OAuthToken) -> None:
        self.ensure_schema()
        payload = json.dumps(asdict(token), ensure_ascii=False)
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO ads_oauth_tokens (tenant_id, platform, account_id, token_json, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(tenant_id, platform, account_id)
                DO UPDATE SET token_json=excluded.token_json, updated_at=datetime('now');
                """,
                (tenant_id, platform, account_id, payload),
            )
            conn.commit()

    def get(self, *, tenant_id: str, platform: str, account_id: str) -> OAuthToken | None:
        self.ensure_schema()
        with self._lock, sqlite3.connect(self._path) as conn:
            cur = conn.execute(
                "SELECT token_json FROM ads_oauth_tokens WHERE tenant_id=? AND platform=? AND account_id=?;",
                (tenant_id, platform, account_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return OAuthToken(**data)

    def delete(self, *, tenant_id: str, platform: str, account_id: str) -> None:
        self.ensure_schema()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                "DELETE FROM ads_oauth_tokens WHERE tenant_id=? AND platform=? AND account_id=?;",
                (tenant_id, platform, account_id),
            )
            conn.commit()
