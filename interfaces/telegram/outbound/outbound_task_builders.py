from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from interfaces.telegram.outbound.outbound_types import OutboundTask


def build_outbound_task(
    *,
    priority: int,
    seq: int,
    kind: str,
    meta: dict[str, Any] | None,
    method: str,
    chat_id: int | None,
    fn: Any,
    critical: bool,
    done: threading.Event | None = None,
    result_box: dict[str, Any] | None = None,
) -> OutboundTask:
    return OutboundTask(
        priority=int(priority),
        seq=int(seq),
        enqueue_t_ns=time.monotonic_ns(),
        kind=str(kind or (meta or {}).get("kind") or "normal"),
        method=str(method),
        chat_id=chat_id,
        fn=fn,
        created_at=time.monotonic(),
        meta=dict(meta or {}),
        done=done,
        result_box=result_box,
        critical=bool(critical),
    )


__all__ = ["build_outbound_task"]
