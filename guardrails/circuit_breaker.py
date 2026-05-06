from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_bool, _as_int, _payload_view


class CircuitBreaker:
    def __init__(self, *, max_consecutive_failures: int = 3) -> None:
        self._max_consecutive_failures = max(1, int(max_consecutive_failures))

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        opened = _as_bool(body.get('circuit_open') or body.get('opened'))
        failures = _as_int(body.get('consecutive_failures', 0), minimum=0)
        if opened or failures >= self._max_consecutive_failures:
            return GuardCheckResult(False, 'circuit_open').as_tuple()
        return GuardCheckResult(True, 'circuit_closed').as_tuple()
