from __future__ import annotations

import hashlib
import json
import time
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
    """Live-canary ledger with incremental reads and late-row reconciliation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        reconcile_interval = float(
            kwargs.pop("reconcile_interval_seconds", 60 * 60)
        )
        if reconcile_interval < 1:
            raise ValueError("reconcile_interval_seconds must be at least one")
        super().__init__(*args, **kwargs)
        self._evidence_lock = Lock()
        self._evidence_cursor_ms = 0
        self._seen_keys_at_cursor: set[str] = set()
        self._materialized_keys: set[str] = set()
        self._materialized_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._reconcile_interval_seconds = reconcile_interval
        self._last_reconcile_monotonic = 0.0

    def _refresh_materialized_rows(self) -> None:
        now = time.monotonic()
        with self._evidence_lock:
            full_reconcile = (
                self._last_reconcile_monotonic <= 0
                or now - self._last_reconcile_monotonic
                >= self._reconcile_interval_seconds
            )
            cursor_ms = 0 if full_reconcile else self._evidence_cursor_ms
        events = list(
            iter_event_window(
                self.event_log,
                start_ms=cursor_ms,
                event_types=LIVE_CANARY_EVENT_TYPES,
            )
        )
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
                if not full_reconcile:
                    if timestamp_ms < self._evidence_cursor_ms:
                        continue
                    if (
                        timestamp_ms == self._evidence_cursor_ms
                        and key in self._seen_keys_at_cursor
                    ):
                        continue
                if self._belongs(event) and key not in self._materialized_keys:
                    self._materialized_keys.add(key)
                    self._materialized_rows.append(
                        (_data(event), _payload(event))
                    )
                if timestamp_ms > self._evidence_cursor_ms:
                    self._evidence_cursor_ms = timestamp_ms
                    self._seen_keys_at_cursor = {key}
                elif timestamp_ms == self._evidence_cursor_ms:
                    self._seen_keys_at_cursor.add(key)
            if full_reconcile:
                self._last_reconcile_monotonic = now

    def _experiment_rows(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        self._refresh_materialized_rows()
        with self._evidence_lock:
            return list(self._materialized_rows)


__all__ = ["LiveCanaryLedger"]
