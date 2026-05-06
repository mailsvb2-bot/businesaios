from __future__ import annotations

from dataclasses import dataclass

from runtime.queue.backpressure_policy import BackpressurePolicy, BackpressureVerdict


CANON_RUNTIME_QUEUE_THROTTLE_POLICY = True


@dataclass(frozen=True)
class ThrottleDecision:
    max_claim_count: int
    reason: str
    suggested_delay_seconds: int = 0
    backpressure: BackpressureVerdict | None = None


class ThrottlePolicy:
    """Computes a safe worker batch size.

    This is a bounded operational policy and never decides job semantics.
    It can optionally tighten throughput under queue backpressure, but it never
    invents or reprioritizes work.
    """

    def __init__(
        self,
        *,
        max_batch_size: int = 50,
        max_concurrency_hint: int = 8,
        backpressure_policy: BackpressurePolicy | None = None,
        pressure_batch_scale_divisor: int = 2,
    ) -> None:
        self._max_batch_size = max(1, int(max_batch_size))
        self._max_concurrency_hint = max(1, int(max_concurrency_hint))
        self._backpressure_policy = backpressure_policy or BackpressurePolicy()
        self._pressure_batch_scale_divisor = max(1, int(pressure_batch_scale_divisor))

    def evaluate(self, *, queue_depth: int, active_claims: int) -> ThrottleDecision:
        depth = max(0, int(queue_depth))
        active = max(0, int(active_claims))
        pressure = self._backpressure_policy.evaluate(queue_depth=depth, claimed_depth=active)
        if depth <= 0:
            return ThrottleDecision(max_claim_count=0, reason="queue_empty", suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)
        if not pressure.allowed:
            return ThrottleDecision(max_claim_count=0, reason=pressure.reason, suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)
        if active >= self._max_concurrency_hint:
            return ThrottleDecision(max_claim_count=1, reason="concurrency_saturated", suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)

        headroom = max(1, self._max_concurrency_hint - active)
        batch = min(self._max_batch_size, depth, headroom * 2)
        if depth > self._max_batch_size * 10:
            return ThrottleDecision(max_claim_count=max(1, self._max_batch_size), reason="queue_pressure", suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)
        if pressure.reason != "normal":
            reduced = max(1, int(batch) // self._pressure_batch_scale_divisor)
            return ThrottleDecision(max_claim_count=reduced, reason=pressure.reason, suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)
        return ThrottleDecision(max_claim_count=max(1, int(batch)), reason="normal", suggested_delay_seconds=pressure.suggested_delay_seconds, backpressure=pressure)

    decide = evaluate


__all__ = [
    "CANON_RUNTIME_QUEUE_THROTTLE_POLICY",
    "ThrottleDecision",
    "ThrottlePolicy",
]
