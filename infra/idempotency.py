from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Callable, TypeVar


T = TypeVar("T")


class IdempotencyInProgressError(RuntimeError):
    def __init__(self, key: str) -> None:
        self.key = str(key)
        super().__init__(f"idempotency key already in progress: {self.key}")


class IdempotencyTerminalFailureError(RuntimeError):
    def __init__(self, key: str, *, reason: str | None = None) -> None:
        self.key = str(key)
        self.reason = str(reason or '').strip() or None
        message = f"idempotency key is terminal failed: {self.key}"
        if self.reason:
            message = f"{message} ({self.reason})"
        super().__init__(message)


@dataclass
class IdempotencyExecutor:
    store: object
    _inflight_keys: set[str] = field(default_factory=set, init=False, repr=False, compare=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    def status(self, *, key: str) -> str:
        status_fn = getattr(self.store, 'status', None)
        if callable(status_fn):
            value = str(status_fn(key)).strip().lower()
            return value or 'missing'
        with self._lock:
            if str(key) in self._inflight_keys:
                return 'in_progress'
        has_fn = getattr(self.store, 'has', None)
        if callable(has_fn) and bool(has_fn(key)):
            return 'completed'
        return 'missing'

    def run(self, *, key: str, fn: Callable[[], T]) -> T:
        reserve = getattr(self.store, 'reserve', None)
        mark_completed = getattr(self.store, 'mark_completed', None)
        mark_failed = getattr(self.store, 'mark_failed', None)
        get_value = getattr(self.store, 'get', None)

        if callable(reserve) and callable(mark_completed) and callable(mark_failed) and callable(get_value):
            decision = reserve(key)
            resolution_obj = getattr(decision, 'resolution', '')
            resolution = str(getattr(resolution_obj, 'value', resolution_obj) or '').strip().lower()
            if resolution == 'replay_completed':
                return get_value(key)  # type: ignore[return-value]
            if resolution == 'rejected_in_progress':
                raise IdempotencyInProgressError(key)
            if resolution == 'rejected_terminal_failed':
                record = getattr(decision, 'record', None)
                reason = getattr(decision, 'reason', None) or getattr(decision, 'failure_reason', None) or getattr(record, 'failure_reason', None)
                raise IdempotencyTerminalFailureError(key, reason=reason)
            if resolution not in {'accepted', ''}:
                raise RuntimeError(f'unexpected idempotency resolution: {resolution}')
            try:
                value = fn()
            except Exception as exc:
                mark_failed(key, reason=str(exc))
                raise
            mark_completed(key, value)
            return value

        has_fn = getattr(self.store, 'has', None)
        put_fn = getattr(self.store, 'put', None)
        if not callable(has_fn) or not callable(get_value) or not callable(put_fn):
            raise TypeError('idempotency store must support either reserve/get/mark_completed/mark_failed or has/get/put')

        if bool(has_fn(key)):
            return get_value(key)  # type: ignore[return-value]

        with self._lock:
            if str(key) in self._inflight_keys:
                raise IdempotencyInProgressError(key)
            self._inflight_keys.add(str(key))
        try:
            value = fn()
            put_fn(key, value)
            return value
        finally:
            with self._lock:
                self._inflight_keys.discard(str(key))
