from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from threading import Lock
from typing import Any

from core.events.log_queries import (
    event_timestamp_ms,
    iter_events as iter_event_window,
)
from core.experiments.events.live_canary_events import LIVE_CANARY_EVENT_TYPES
from core.experiments.repositories.live_canary_ledger import (
    LiveCanaryLedger as _BaseLiveCanaryLedger,
)


def _data(event: Any) -> dict[str, Any]:
    return dict(event) if isinstance(event, Mapping) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


def _event_key(event: Any) -> str:
    data = _data(event)
    digest = hashlib.sha256(
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return digest


class LiveCanaryLedger(_BaseLiveCanaryLedger):
    """Live-canary ledger with an incremental materialized evidence view."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._evidence_lock = Lock()
        self._evidence_cursor_ms = 0
        self._seen_keys_at_cursor: set[str] = set()
        self._materialized_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def _refresh_materialized_rows(self) -> None:
        with self._evidence_lock:
            cursor_ms = self._evidence_cursor_ms
            seen_at_cursor = set(self._seen_keys_at_cursor)
        events = [
            event
            for event in iter_event_window(
                self.event_log,
                start_ms=cursor_ms,
                event_types=LIVE_CANARY_EVENT_TYPES,
            )
            if self._belongs(event)
        ]
        events.sort(
            key=lambda event: (
                event_timestamp_ms(event),
                _event_key(event),
            )
        )
        with self._evidence_lock:
            for event in events:
                timestamp_ms = event_timestamp_ms(event)
                key = _event_key(event)
                if timestamp_ms < self._evidence_cursor_ms:
                    continue
                if (
                    timestamp_ms == self._evidence_cursor_ms
                    and key in self._seen_keys_at_cursor
                ):
                    continue
                self._materialized_rows.append((_data(event), _payload(event)))
                if timestamp_ms > self._evidence_cursor_ms:
                    self._evidence_cursor_ms = timestamp_ms
                    self._seen_keys_at_cursor = {key}
                else:
                    self._seen_keys_at_cursor.add(key)
            if self._evidence_cursor_ms == cursor_ms:
                self._seen_keys_at_cursor.update(seen_at_cursor)

    def _experiment_rows(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        self._refresh_materialized_rows()
        with self._evidence_lock:
            return list(self._materialized_rows)


__all__ = ["LiveCanaryLedger"]
