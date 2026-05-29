from __future__ import annotations

"""Retention ports.

This module exists to keep core.retention independent from concrete storage
implementations.

The production repo currently uses SqliteEventStore which provides these methods.
Core code MUST depend on this Protocol only (no platform_layer imports).
"""

from typing import Any, Dict, Iterable, Iterator, Optional, Protocol, Tuple


class RetentionStore(Protocol):
    # Event stream
    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int,
        user_id: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> Iterable[dict[str, Any]]: ...

    def latest_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> Iterable[dict[str, Any]]: ...

    # Retention feature snapshots
    def upsert_user_features_daily(
        self,
        *,
        tenant_id: str,
        user_id: str,
        day_key: str,
        features_json: str,
        now_ms: int,
    ) -> None: ...

    # Bandit state
    def bandit_ensure_arm(self, *, tenant_id: str, arm: str, now_ms: int) -> None: ...

    def bandit_get_arm(self, *, tenant_id: str, arm: str) -> tuple[int, int]: ...

    def bandit_update_arm(self, *, tenant_id: str, arm: str, success: bool, now_ms: int) -> None: ...
