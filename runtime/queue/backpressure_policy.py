from __future__ import annotations

from dataclasses import dataclass


CANON_RUNTIME_QUEUE_BACKPRESSURE_POLICY = True


@dataclass(frozen=True)
class BackpressureVerdict:
    allowed: bool
    reason: str
    suggested_delay_seconds: int = 0


class BackpressurePolicy:
    """Operational admission guard for queue pressure.

    This layer is intentionally dumb: it only looks at queue volume.
    """

    def __init__(
        self,
        *,
        queue_soft_limit: int = 1_000,
        queue_hard_limit: int = 5_000,
        claimed_soft_limit: int = 250,
        claimed_hard_limit: int = 1_000,
    ) -> None:
        self._queue_soft_limit = max(1, int(queue_soft_limit))
        self._queue_hard_limit = max(self._queue_soft_limit, int(queue_hard_limit))
        self._claimed_soft_limit = max(1, int(claimed_soft_limit))
        self._claimed_hard_limit = max(self._claimed_soft_limit, int(claimed_hard_limit))

    def evaluate(self, *, queue_depth: int, claimed_depth: int = 0) -> BackpressureVerdict:
        depth = max(0, int(queue_depth))
        claimed = max(0, int(claimed_depth))
        total = depth + claimed

        if depth >= self._queue_hard_limit or claimed >= self._claimed_hard_limit:
            return BackpressureVerdict(False, "queue_hard_limit_reached", 60)
        if total >= self._queue_hard_limit:
            return BackpressureVerdict(False, "queue_total_hard_limit_reached", 60)
        if depth >= self._queue_soft_limit or claimed >= self._claimed_soft_limit:
            return BackpressureVerdict(True, "queue_soft_pressure", 5)
        return BackpressureVerdict(True, "normal", 0)


__all__ = [
    "BackpressurePolicy",
    "BackpressureVerdict",
    "CANON_RUNTIME_QUEUE_BACKPRESSURE_POLICY",
]
