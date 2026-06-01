from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional

import runtime.platform.event_store.sqlite_read_queries as _rq


class SqliteEventStoreQueryApi:
    """Read/query API for SqliteEventStore."""

    _db: sqlite3.Connection | None

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms=None,
        event_type=None,
        user_id=None,
    ) -> Iterable[dict[str, Any]]:
        assert self._db is not None
        return _rq.iter_events(
            self._db,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            event_type=event_type,
            user_id=user_id,
        )

    def latest_event(
        self,
        *,
        tenant_id: str = "default",
        user_id=None,
        event_types=None,
    ) -> dict[str, Any] | None:
        assert self._db is not None
        return _rq.latest_event(
            self._db,
            tenant_id=tenant_id,
            user_id=user_id,
            event_types=event_types,
        )

    def latest_events(
        self,
        *,
        tenant_id: str = "default",
        user_id=None,
        event_type=None,
        event_types=None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        assert self._db is not None
        return _rq.latest_events(
            self._db,
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            event_types=event_types,
            limit=limit,
        )

    def count_distinct_users(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms=None,
        event_type=None,
        exclude_system: bool = True,
    ) -> int:
        assert self._db is not None
        return _rq.count_distinct_users(
            self._db,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            event_type=event_type,
            exclude_system=exclude_system,
        )

    def recent_user_ids(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms=None,
        limit: int = 20,
        exclude_system: bool = True,
    ) -> list[tuple[str, int]]:
        assert self._db is not None
        return _rq.recent_user_ids(
            self._db,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
            exclude_system=exclude_system,
        )

    def count_events(
        self,
        *,
        tenant_id: str,
        event_type: str,
        start_ms: int = 0,
        end_ms=None,
        user_id=None,
    ) -> int:
        assert self._db is not None
        return _rq.count_events(
            self._db,
            tenant_id=tenant_id,
            event_type=event_type,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
        )

    def get_counter(self, *, event_type: str, user_id=None) -> int:
        assert self._db is not None
        return _rq.get_counter(self._db, event_type=event_type, user_id=user_id)

    def sum_event_payload_int(
        self,
        *,
        tenant_id: str,
        event_type: str,
        field: str,
        start_ms: int = 0,
        end_ms=None,
        user_id=None,
    ) -> int:
        assert self._db is not None
        return _rq.sum_event_payload_int(
            self._db,
            tenant_id=tenant_id,
            event_type=event_type,
            field=field,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
        )

    def count_active_users_min_days(
        self,
        *,
        tenant_id: str,
        lookback_days: int,
        min_active_days: int = 2,
    ) -> int:
        assert self._db is not None
        return _rq.count_active_users_min_days(
            self._db,
            tenant_id=tenant_id,
            lookback_days=lookback_days,
            min_active_days=min_active_days,
        )

    def count_events_payload_like(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload_substring: str,
        start_ms: int = 0,
        end_ms=None,
    ) -> int:
        assert self._db is not None
        return _rq.count_events_payload_like(
            self._db,
            tenant_id=tenant_id,
            event_type=event_type,
            payload_substring=payload_substring,
            start_ms=start_ms,
            end_ms=end_ms,
        )

    def count_distinct_users_payload_like(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload_substring: str,
        start_ms: int = 0,
        end_ms=None,
    ) -> int:
        assert self._db is not None
        return _rq.count_distinct_users_payload_like(
            self._db,
            tenant_id=tenant_id,
            event_type=event_type,
            payload_substring=payload_substring,
            start_ms=start_ms,
            end_ms=end_ms,
        )
