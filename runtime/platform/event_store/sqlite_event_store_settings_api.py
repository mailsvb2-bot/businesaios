from __future__ import annotations

import json
import sqlite3


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
    def compare_and_set_setting(self, *, tenant_id: str, key: str, expected, value) -> bool:
        assert self._db is not None
        import time
        encoded, now = json.dumps(value, ensure_ascii=False, sort_keys=True), int(time.time() * 1000)
        if expected is None:
            cur = self._db.execute("INSERT INTO settings(tenant_id,key,value_json,updated_at_ms) VALUES (?,?,?,?) ON CONFLICT(tenant_id,key) DO NOTHING", (str(tenant_id), str(key), encoded, now))
        else:
            cur = self._db.execute("UPDATE settings SET value_json=?, updated_at_ms=? WHERE tenant_id=? AND key=? AND value_json=?", (encoded, now, str(tenant_id), str(key), json.dumps(expected, ensure_ascii=False, sort_keys=True)))
        self._db.commit()
        return int(cur.rowcount or 0) == 1
