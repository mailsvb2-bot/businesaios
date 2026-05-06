from __future__ import annotations

import time
from typing import Any, Dict

from core.observability.silent import swallow


def maybe_emit_queue_high_warning(queue_obj: Any, *, qsize: int, method: str, meta: Dict[str, Any] | None) -> None:
    if qsize < int(queue_obj._warn_queue):
        return
    now_ns = time.monotonic_ns()
    if now_ns < int(queue_obj._next_queue_high_log_ns):
        return

    queue_obj._next_queue_high_log_ns = now_ns + int(queue_obj._alert_min_interval_ns)
    safe_meta = {
        key: value
        for key, value in (meta or {}).items()
        if key in {"kind", "priority", "chat_id", "user_id", "purpose", "action"}
    }
    queue_obj._emit("telegram_outbound_queue_high", {"qsize": int(qsize), "method": method, **safe_meta})
    try:
        queue_obj._log.warning("[tg-outbound] queue high: %s", qsize)
    except Exception:
        swallow(__name__, "outbound_queue.enqueue.log")
