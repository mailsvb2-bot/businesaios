from __future__ import annotations

from dataclasses import dataclass, field


CANON_MARKET_INTELLIGENCE_CIRCUIT_BREAKER = True


@dataclass
class MarketIntelligenceCircuitBreaker:
    failure_threshold: int = 3
    half_open_after_failures: int = 0
    _failures: dict[str, int] = field(default_factory=dict)
    _half_open_budget: dict[str, int] = field(default_factory=dict)

    def ensure_open(self, provider: str) -> None:
        key = str(provider).strip()
        failures = int(self._failures.get(key, 0))
        if failures < int(self.failure_threshold):
            return
        budget = int(self._half_open_budget.get(key, self.half_open_after_failures))
        if budget <= 0:
            raise ValueError(f'provider circuit open: {key}')
        self._half_open_budget[key] = budget - 1

    def on_success(self, provider: str) -> None:
        key = str(provider).strip()
        self._failures.pop(key, None)
        self._half_open_budget.pop(key, None)

    def on_failure(self, provider: str) -> None:
        key = str(provider).strip()
        self._failures[key] = int(self._failures.get(key, 0)) + 1
        if self._failures[key] >= int(self.failure_threshold):
            self._half_open_budget[key] = int(self.half_open_after_failures)

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {
            'failures': dict(self._failures),
            'half_open_budget': dict(self._half_open_budget),
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_CIRCUIT_BREAKER', 'MarketIntelligenceCircuitBreaker']
