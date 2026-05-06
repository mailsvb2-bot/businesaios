from __future__ import annotations

"""Cooperative stop token for runtime queue worker loops.

Operational only:
- supports graceful shutdown of polling workers
- does not decide what work exists
- does not change canonical execution semantics
"""

from dataclasses import dataclass
from datetime import datetime
from threading import Event

from runtime.queue.job_contract import normalize_now


CANON_RUNTIME_QUEUE_STOP_TOKEN = True


@dataclass(frozen=True)
class StopRequest:
    requested_at: datetime
    hard: bool = False
    reason: str = "shutdown_requested"


class JobStopToken:
    def __init__(self) -> None:
        self._event = Event()
        self._request: StopRequest | None = None

    @property
    def request(self) -> StopRequest | None:
        return self._request

    def is_stop_requested(self) -> bool:
        return self._event.is_set()

    def request_stop(
        self,
        *,
        reason: str = "shutdown_requested",
        hard: bool = False,
        now: datetime | None = None,
    ) -> StopRequest:
        request = StopRequest(
            requested_at=normalize_now(now),
            hard=bool(hard),
            reason=str(reason).strip() or "shutdown_requested",
        )
        self._request = request
        self._event.set()
        return request

    def wait(self, timeout_seconds: float) -> bool:
        return self._event.wait(max(0.0, float(timeout_seconds)))


__all__ = [
    "CANON_RUNTIME_QUEUE_STOP_TOKEN",
    "JobStopToken",
    "StopRequest",
]
