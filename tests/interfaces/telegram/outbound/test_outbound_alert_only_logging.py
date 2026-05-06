import logging
import threading
import time

import pytest

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


def test_alert_only_no_log_in_normal_conditions():
    lines: list[str] = []
    lock = threading.Lock()

    def logger(s: str) -> None:
        with lock:
            lines.append(s)

    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=100,
        warn_queue=10_000,  # effectively disabled
        emit_event=None,
        log=logging.getLogger("test.outbound"),
        overflow_policy="block",
        alert_ux_wait_p95_ms=9999.0,  # effectively disabled
        alert_drop_best_effort=True,
        alert_qsize=9999,  # disabled
        alert_min_interval_s=0.1,
        metrics_logger=logger,
    )

    try:
        done = threading.Event()

        def fn():
            done.set()

        ok = q.enqueue_ux(method="sendMessage", chat_id=1, fn=fn, critical=True)
        assert ok is True
        assert done.wait(timeout=1.0)

        # No drop, no qsize overflow, SLA threshold huge => no alerts expected.
        time.sleep(0.1)
        with lock:
            assert len(lines) == 0

    finally:
        q.stop()


def test_alert_emits_on_best_effort_drop_and_throttles():
    lines: list[str] = []
    lock = threading.Lock()
    emitted = threading.Event()

    def logger(s: str) -> None:
        with lock:
            lines.append(s)
            emitted.set()

    # max_queue=1 -> force drops easily
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1,
        warn_queue=10_000,
        emit_event=None,
        log=logging.getLogger("test.outbound"),
        overflow_policy="drop",
        alert_ux_wait_p95_ms=0.0,  # disabled
        alert_drop_best_effort=True,  # enabled
        alert_qsize=0,  # disabled
        alert_min_interval_s=0.3,  # throttle window
        metrics_logger=logger,
    )

    try:
        # Fill queue with a long task so it's full.
        hold = threading.Event()

        def long_fn():
            hold.wait(timeout=1.0)

        ok1 = q.enqueue_ux(method="sendMessage", chat_id=1, fn=long_fn, critical=True)
        assert ok1 is True

        # Now drop best-effort marketing.
        ok2 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok2 is False  # dropped due to full

        # Should emit an alert soon (drop condition).
        assert emitted.wait(timeout=1.0)

        with lock:
            first_count = len(lines)
            first_line = lines[-1]

        assert "[ALERT:" in first_line
        assert "DROPS_BEST_EFFORT" in first_line

        # More drops inside throttle window should NOT produce more lines.
        emitted.clear()
        for _ in range(5):
            q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        time.sleep(0.1)
        with lock:
            assert len(lines) == first_count

        # After throttle window, another drop should emit another alert.
        time.sleep(0.35)
        q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert emitted.wait(timeout=1.0)
        with lock:
            assert len(lines) == first_count + 1

        hold.set()

    finally:
        q.stop()
