from __future__ import annotations

import json
import sqlite3
from typing import Optional

from runtime.platform.event_store.append_contract import normalize_append_event
import runtime.platform.event_store.sqlite_write_helpers as _wh


class SqliteEventStoreWriteApi:
    """Write-path API for SqliteEventStore."""

    _db: Optional[sqlite3.Connection]

    def append_event(self, event: dict, *, commit: bool = True) -> None:
        assert self._db is not None
        append = normalize_append_event(event)
        self._db.execute(
            "INSERT INTO events(event_id,tenant_id,user_id,source,event_type,timestamp_ms,decision_id,correlation_id,payload_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                append.event_id,
                append.tenant_id,
                append.user_id,
                append.source,
                append.event_type,
                append.timestamp_ms,
                append.decision_id,
                append.correlation_id,
                json.dumps(append.payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        _wh._append_counters(
            self._db,
            event_type=append.event_type,
            user_id=append.user_id,
            ts=append.timestamp_ms,
        )
        _wh._append_user_state(
            self._db,
            tenant_id=append.tenant_id,
            user_id=append.user_id,
            event_type=append.event_type,
            ts=append.timestamp_ms,
            payload_obj=dict(append.payload),
        )
        if commit:
            self._db.commit()
