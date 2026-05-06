from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SetIdempotencyGate:
    _seen: set[str] = field(default_factory=set)

    def claim(self, key: str) -> bool:
        normalized = str(key)
        if normalized in self._seen:
            return False
        self._seen.add(normalized)
        return True


@dataclass(frozen=True)
class StatusRetryPolicy:
    terminal_status: str = 'ok'
    max_attempts: int = 1

    def should_retry(self, *, attempt: int, status: object) -> bool:
        normalized_status = str(status)
        return normalized_status != self.terminal_status and int(attempt) < int(self.max_attempts)


@dataclass(frozen=True)
class RetryableStatusSet:
    statuses: frozenset[str] = frozenset()

    def should_retry(self, status: object) -> bool:
        return str(status) in self.statuses
