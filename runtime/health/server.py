"""Runtime health snapshot (NO network bindings).

Per System TZ:
- All real integrations (network servers, SDKs, DB drivers) live only in: runtime/_internal/_effects_impl.py
- This module is pure data aggregation from EventLog.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from runtime.observability.error_handling import exception_throttled

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


class HealthSnapshot:
    """Collects health indicators from the event log.

    This is intentionally *read-only* and contains no I/O.
    """

    def __init__(self, *, event_log: Any, name: str = "runtime") -> None:
        self._event_log = event_log
        self._name = str(name)

    def collect(self) -> dict[str, Any]:
        events, total_events = [], 0
        try:
            events, total_events = self._event_log.health_events()
        except Exception:
            exception_throttled(logger, key="health_snapshot_collect", msg="health snapshot collection failed")
        latest = {str(ev.get("event_type") or ""): ev for ev in events if isinstance(ev, dict)}
        def timestamp(event: dict[str, Any]) -> int | None:
            try:
                return int(event.get("timestamp_ms") or 0) or None
            except (TypeError, ValueError, OverflowError):
                return None
        poll = latest.get("telegram_polled", {})
        error = latest.get("telegram_poll_error", {})
        decision = latest.get("decision_executed", {})
        return {
            "name": self._name, "ts_ms": _now_ms(),
            "telegram": {
                "last_poll_ms": timestamp(poll),
                "last_poll_error_ms": timestamp(error),
                "last_poll_error": str(error.get("payload") or error.get("error") or "") if error else None,
            },
            "ring": {"last_decision_executed_ms": timestamp(decision)},
            "total_events": total_events,
        }
