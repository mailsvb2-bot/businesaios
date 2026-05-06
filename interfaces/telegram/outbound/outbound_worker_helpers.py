from __future__ import annotations

import time
from typing import Any, Dict

from interfaces.telegram.outbound.outbound_types import OutboundTask
from interfaces.telegram.outbound.rate_limit import TokenBucket


def record_task_metrics(*, metrics: Any, task: OutboundTask, start_exec_ns: int) -> None:
    end_ns = time.monotonic_ns()
    wait_ms = (int(start_exec_ns) - int(task.enqueue_t_ns)) / 1_000_000.0
    exec_ms = (end_ns - int(start_exec_ns)) / 1_000_000.0
    metrics.record(int(task.priority), float(wait_ms), float(exec_ms))


def get_or_create_chat_bucket(
    *,
    per_chat: Dict[int, TokenBucket],
    chat_id: int,
    chat_burst: int,
    chat_rps: float,
) -> TokenBucket:
    bucket = per_chat.get(int(chat_id))
    if bucket is None:
        bucket = TokenBucket(capacity=int(chat_burst), refill_per_s=float(chat_rps))
        per_chat[int(chat_id)] = bucket
    return bucket


__all__ = [
    "get_or_create_chat_bucket",
    "record_task_metrics",
]
