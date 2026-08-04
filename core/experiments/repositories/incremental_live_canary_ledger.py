from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from threading import Lock
from typing import Any

from core.events.log_queries import (
    direct_latest_append_seq,
    event_append_seq,
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
    """Live-canary ledger materialized by durable store append order."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._evidence_lock = Lock()
        self._append_cursor = 0
        self._materialized_keys: set[str] = set()
        self._materialized_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def _refresh_materialized_rows(self) -> None:
        tail = direct_latest_append_seq(self.event_log)
        with self._evidence_lock:
            after_append_seq = self._append_cursor
        if tail is not None and tail <= after_append_seq:
            return
        events = list(
            iter_event_window(
                self.event_log,
                start_ms=0,
                after_append_seq=after_append_seq,
                event_types=LIVE_CANARY_EVENT_TYPES,
            )
        )
        events.sort(key=lambda event: (event_append_seq(event), _event_key(event)))
        with self._evidence_lock:
            for event in events:
                append_seq = event_append_seq(event)
                if append_seq <= self._append_cursor:
                    continue
                key = _event_key(event)
                if self._belongs(event) and key not in self._materialized_keys:
                    self._materialized_keys.add(key)
                    self._materialized_rows.append(
                        (_data(event), _payload(event))
                    )
                self._append_cursor = append_seq
            if tail is not None:
                self._append_cursor = max(self._append_cursor, tail)

    def _experiment_rows(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        self._refresh_materialized_rows()
        with self._evidence_lock:
            return list(self._materialized_rows)


__all__ = ["LiveCanaryLedger"]
