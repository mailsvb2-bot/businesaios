"""Test: throttled_logger thread safety and correctness."""

from __future__ import annotations

import logging
import threading
import time

from core.observability.throttled_logger import (
    _LOCK,
    _should_emit,
    exception_throttled,
    warning_throttled,
)


def test_should_emit_respects_throttle():
    """First call emits, second within window does not."""
    key = f"test_throttle_{time.time()}"
    assert _should_emit(key, 5000) is True
    assert _should_emit(key, 5000) is False


def test_should_emit_different_keys_independent():
    """Different keys have independent throttle windows."""
    k1 = f"test_a_{time.time()}"
    k2 = f"test_b_{time.time()}"
    assert _should_emit(k1, 5000) is True
    assert _should_emit(k2, 5000) is True
    assert _should_emit(k1, 5000) is False
    assert _should_emit(k2, 5000) is False


def test_exception_throttled_does_not_raise():
    """exception_throttled must never raise, even with bad inputs."""
    log = logging.getLogger("test.throttled")
    try:
        raise ValueError("test error")
    except ValueError:
        # Should not raise
        exception_throttled(log, key="test_safe", msg="test message")
        exception_throttled(log, key="", msg="")
        exception_throttled(log, key="test_safe", msg="test message", throttle_ms=0)


def test_warning_throttled_does_not_raise():
    """warning_throttled must never raise."""
    log = logging.getLogger("test.throttled.warn")
    warning_throttled(log, key="test_warn", msg="test warning")
    warning_throttled(log, key="", msg="")


def test_thread_safety_no_crash():
    """Concurrent calls from multiple threads must not crash."""
    errors: list[Exception] = []
    barrier = threading.Barrier(10)

    def worker(thread_id: int) -> None:
        try:
            barrier.wait(timeout=5)
            for i in range(100):
                _should_emit(f"thread_{thread_id}_{i}", 1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Thread safety violation: {errors}"


def test_lock_exists():
    """The module must use a threading lock for _LAST_MS access."""
    assert isinstance(_LOCK, type(threading.Lock()))
