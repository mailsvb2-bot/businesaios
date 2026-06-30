"""Outbound queue data types.

Extracted from outbound_queue.py to eliminate god-module.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

PriorityArg = int | str

@dataclass
class OutboundTask:
    """Single outbound Telegram task."""

    # Lower number = higher priority.
    priority: int
    # Monotonic sequence to preserve FIFO within same priority.
    seq: int

    # When the task was enqueued (monotonic ns)
    enqueue_t_ns: int

    method: str
    chat_id: int | None
    fn: Callable[[], Any]
    created_at: float
    meta: dict[str, Any]

    # Logical kind/label (ux/system/payments/marketing/bulk/analytics/normal)
    kind: str = "normal"

    # Completion (used by call())
    done: threading.Event | None = None
    result_box: dict[str, Any] | None = None

    # If False: best-effort (may be dropped under overload).
    critical: bool = True
