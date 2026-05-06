from __future__ import annotations
"""Outbound queue data types.

Extracted from outbound_queue.py to eliminate god-module.
"""

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union

PriorityArg = Union[int, str]


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
    chat_id: Optional[int]
    fn: Callable[[], Any]
    created_at: float
    meta: Dict[str, Any]

    # Logical kind/label (ux/system/payments/marketing/bulk/analytics/normal)
    kind: str = "normal"

    # Completion (used by call())
    done: Optional[threading.Event] = None
    result_box: Optional[Dict[str, Any]] = None

    # If False: best-effort (may be dropped under overload).
    critical: bool = True
