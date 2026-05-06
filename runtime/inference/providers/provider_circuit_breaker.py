from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_RUNTIME_INFERENCE_PROVIDER_CIRCUIT_BREAKER = True


@dataclass
class _ProviderCircuitBreakerState:
    failure_count: int = 0
    open_until_ts: float = 0.0
    half_open: bool = False


class ProviderCircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, open_seconds: int = 60) -> None:
        self._failure_threshold = max(1, int(failure_threshold))
        self._open_seconds = max(1, int(open_seconds))
        self._states: dict[str, _ProviderCircuitBreakerState] = {}

    def allows(self, provider_name: str) -> bool:
        breaker_state = self._states.get(provider_name, _ProviderCircuitBreakerState())
        now = time()
        if now >= breaker_state.open_until_ts:
            if breaker_state.open_until_ts > 0.0:
                breaker_state.half_open = True
                self._states[provider_name] = breaker_state
            return True
        return False

    def record_success(self, provider_name: str) -> None:
        self._states[provider_name] = _ProviderCircuitBreakerState()

    def record_failure(self, provider_name: str) -> None:
        breaker_state = self._states.setdefault(provider_name, _ProviderCircuitBreakerState())
        breaker_state.failure_count = 1 if breaker_state.half_open else breaker_state.failure_count + 1
        breaker_state.half_open = False
        if breaker_state.failure_count >= self._failure_threshold:
            breaker_state.open_until_ts = time() + self._open_seconds
