from __future__ import annotations

"""Runtime health snapshot (NO network bindings).

Per System TZ:
- All real integrations (network servers, SDKs, DB drivers) live only in: runtime/_internal/_effects_impl.py
- This module is pure data aggregation from EventLog.
"""

import logging
import time
from typing import Any, Dict, Optional

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

    def collect(self) -> Dict[str, Any]:
        last_poll_ms: Optional[int] = None
        last_poll_err_ms: Optional[int] = None
        last_poll_err: Optional[str] = None
        last_decision_exec_ms: Optional[int] = None
        total_events = 0

        try:
            for ev in self._event_log.iter_events():
                if not isinstance(ev, dict):
                    continue
                total_events += 1
                et = str(ev.get("event_type") or "")
                ts = int(ev.get("timestamp_ms") or 0)
                if et == "telegram_polled":
                    last_poll_ms = max(last_poll_ms or 0, ts)
                elif et == "telegram_poll_error":
                    last_poll_err_ms = max(last_poll_err_ms or 0, ts)
                    last_poll_err = str(ev.get("payload") or ev.get("error") or "")
                elif et == "decision_executed":
                    last_decision_exec_ms = max(last_decision_exec_ms or 0, ts)
        except Exception:
            exception_throttled(
                logger,
                key="health_snapshot_collect",
                msg="health snapshot collection failed",
            )

        out: Dict[str, Any] = {
            "name": self._name,
            "ts_ms": _now_ms(),
            "telegram": {
                "last_poll_ms": last_poll_ms,
                "last_poll_error_ms": last_poll_err_ms,
                "last_poll_error": last_poll_err,
            },
            "ring": {
                "last_decision_executed_ms": last_decision_exec_ms,
            },
            "total_events": total_events,
        }
        return out
