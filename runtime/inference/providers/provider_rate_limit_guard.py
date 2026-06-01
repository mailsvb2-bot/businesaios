from __future__ import annotations

from dataclasses import dataclass, field
from time import time

CANON_RUNTIME_INFERENCE_PROVIDER_RATE_LIMIT_GUARD = True


@dataclass
class _RateWindow:
    started_at: float = field(default_factory=time)
    count: int = 0


class ProviderRateLimitGuard:
    def __init__(self, *, max_requests_per_minute: int = 120) -> None:
        self._max_requests_per_minute = max(0, int(max_requests_per_minute))
        self._windows: dict[str, _RateWindow] = {}

    def allows(self, provider_name: str) -> bool:
        window = self._windows.setdefault(provider_name, _RateWindow())
        now = time()
        if now - window.started_at >= 60.0:
            window.started_at = now
            window.count = 0
        return window.count < self._max_requests_per_minute

    def record(self, provider_name: str) -> None:
        if not self.allows(provider_name):
            raise RuntimeError(f"rate limit exceeded for provider '{provider_name}'")
        window = self._windows.setdefault(provider_name, _RateWindow())
        now = time()
        if now - window.started_at >= 60.0:
            window.started_at = now
            window.count = 0
        window.count += 1
