from __future__ import annotations

import json
import sqlite3
from typing import Optional


class SqliteEventStoreSettingsApi:
    """Settings API for SqliteEventStore."""

    _db: sqlite3.Connection | None

    def get_setting(self, *, tenant_id: str, key: str):
        assert self._db is not None
        row = self._db.execute(
            "SELECT value_json FROM settings WHERE tenant_id=? AND key=?",
            (str(tenant_id), str(key)),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(str(row[0] or "{}"))
        except Exception:
            return None

    def set_setting(
        self,
        *,
        tenant_id: str,
        key: str,
        value,
        commit: bool = True,
    ) -> None:
        assert self._db is not None
        import time

        self._db.execute(
            "INSERT INTO settings(tenant_id,key,value_json,updated_at_ms) VALUES (?,?,?,?) "
            "ON CONFLICT(tenant_id,key) DO UPDATE SET value_json=excluded.value_json, updated_at_ms=excluded.updated_at_ms",
            (
                str(tenant_id),
                str(key),
                json.dumps(value, ensure_ascii=False, sort_keys=True),
                int(time.time() * 1000),
            ),
        )
        if commit:
            self._db.commit()
