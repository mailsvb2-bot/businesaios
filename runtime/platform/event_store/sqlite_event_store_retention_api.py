from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

import runtime.platform.event_store.sqlite_retention as _ret
import runtime.platform.event_store.sqlite_user_state as _us


class SqliteEventStoreRetentionApi:
    """User-state and retention/bandit API for SqliteEventStore."""

    _db: sqlite3.Connection | None

    def get_user_state(
        self,
        *,
        tenant_id: str = "default",
        user_id: str,
    ) -> dict[str, Any]:
        assert self._db is not None
        return _us.get_user_state(self._db, tenant_id=tenant_id, user_id=user_id)

    def delete_user_events(self, *, tenant_id: str, user_id: str) -> int:
        assert self._db is not None
        return _us.delete_user_events(self._db, tenant_id=tenant_id, user_id=user_id)

    def upsert_user_features_daily(
        self,
        *,
        tenant_id: str,
        user_id: str,
        day_key: str,
        features_json: str,
        created_at_ms: int,
    ) -> None:
        assert self._db is not None
        _ret.upsert_user_features_daily(
            self._db,
            tenant_id=tenant_id,
            user_id=user_id,
            day_key=day_key,
            features_json=features_json,
            created_at_ms=created_at_ms,
        )

    def get_user_features_daily(
        self,
        *,
        tenant_id: str,
        user_id: str,
        day_key: str,
    ) -> str | None:
        assert self._db is not None
        return _ret.get_user_features_daily(
            self._db,
            tenant_id=tenant_id,
            user_id=user_id,
            day_key=day_key,
        )

    def bandit_ensure_arm(self, *, tenant_id: str, arm: str, now_ms: int) -> None:
        assert self._db is not None
        _ret.bandit_ensure_arm(self._db, tenant_id=tenant_id, arm=arm, now_ms=now_ms)

    def bandit_get_arm(self, *, tenant_id: str, arm: str) -> tuple[float, float]:
        assert self._db is not None
        return _ret.bandit_get_arm(self._db, tenant_id=tenant_id, arm=arm)

    def bandit_update_arm(
        self,
        *,
        tenant_id: str,
        arm: str,
        success: bool,
        now_ms: int,
    ) -> None:
        assert self._db is not None
        _ret.bandit_update_arm(
            self._db,
            tenant_id=tenant_id,
            arm=arm,
            success=success,
            now_ms=now_ms,
        )

    def try_lock_job(self, *, tenant_id: str, job_key: str, now_ms: int) -> bool:
        assert self._db is not None
        return _ret.try_lock_job(
            self._db,
            tenant_id=tenant_id,
            job_key=job_key,
            now_ms=now_ms,
        )
