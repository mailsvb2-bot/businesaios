from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional
from observability.platform.observability.silent import swallow


DDL = """
CREATE TABLE IF NOT EXISTS offer_cooldowns (
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  offer_id TEXT NOT NULL,
  last_shown_ms INTEGER NOT NULL,
  PRIMARY KEY (tenant_id, user_id, offer_id)
);
"""


@dataclass
class OfferCooldownStoreSqlite:
    """SQLite store for offer cooldowns.

    Allowed location: observability/platform/snapshot_store/.
    """

    path: str
    _conn: Optional[sqlite3.Connection] = None

    def open(self) -> "OfferCooldownStoreSqlite":
        if self._conn is not None:
            return self
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        try:
            self._conn.execute("PRAGMA busy_timeout=5000;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            swallow(__name__, 'observability/platform/snapshot_store/offer_cooldowns_sqlite.py')
        self._conn.executescript(DDL)
        self._conn.commit()
        return self

    def close(self) -> None:
        try:
            if self._conn is not None:
                self._conn.close()
        finally:
            self._conn = None

    def get_last_shown_ms(self, *, tenant_id: str, user_id: str, offer_id: str) -> Optional[int]:
        if self._conn is None:
            raise RuntimeError("COOLDOWN_STORE_NOT_OPEN")
        cur = self._conn.execute(
            "SELECT last_shown_ms FROM offer_cooldowns WHERE tenant_id=? AND user_id=? AND offer_id=?",
            (str(tenant_id), str(user_id), str(offer_id)),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None

    def mark_shown_now(self, *, tenant_id: str, user_id: str, offer_id: str, now_ms: Optional[int] = None) -> None:
        if self._conn is None:
            raise RuntimeError("COOLDOWN_STORE_NOT_OPEN")
        ts = int(now_ms if now_ms is not None else int(time.time() * 1000))
        self._conn.execute(
            "INSERT INTO offer_cooldowns(tenant_id,user_id,offer_id,last_shown_ms) VALUES (?,?,?,?) "
            "ON CONFLICT(tenant_id,user_id,offer_id) DO UPDATE SET last_shown_ms=excluded.last_shown_ms",
            (str(tenant_id), str(user_id), str(offer_id), int(ts)),
        )
        self._conn.commit()