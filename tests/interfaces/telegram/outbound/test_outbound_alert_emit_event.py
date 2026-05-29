import logging
import threading
import time

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


def test_alert_emits_event_and_throttles():
    events: list[tuple[str, dict]] = []
    lock = threading.Lock()
    emitted = threading.Event()

    def emit_event(event_type: str, payload: dict) -> None:
        with lock:
            events.append((event_type, payload))
            emitted.set()

    # max_queue=1 to force best-effort drops -> alert condition
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1,
        warn_queue=10_000,
        emit_event=emit_event,
        log=logging.getLogger("test.outbound"),
        overflow_policy="drop",
        alert_ux_wait_p95_ms=0.0,
        alert_drop_best_effort=True,
        alert_qsize=0,
        alert_min_interval_s=0.4,
        metrics_logger=lambda s: None,
    )

    try:
        hold = threading.Event()

        def long_fn():
            hold.wait(timeout=1.0)

        ok = q.enqueue_ux(method="sendMessage", chat_id=1, fn=long_fn, critical=True)
        assert ok is True

        # This marketing enqueue should drop and trigger alert -> event
        ok2 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok2 is False

        assert emitted.wait(timeout=1.0)

        with lock:
            alerts = [(et, pl) for (et, pl) in events if et == "telegram_outbound_alert"]
            assert len(alerts) == 1
            et, pl = alerts[0]

        assert et == "telegram_outbound_alert"
        assert "reason" in pl
        assert "qsize" in pl
        assert "dropped_best_effort_window" in pl

        # More drops within throttle window => no new event
        emitted.clear()
        for _ in range(5):
            q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        time.sleep(0.1)
        with lock:
            alerts = [(et, pl) for (et, pl) in events if et == "telegram_outbound_alert"]
            assert len(alerts) == 1

        # After throttle window -> new drop => new event
        time.sleep(0.65)
        q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)

        # Alert emission is best-effort; allow a short window for the logger/event to run.
        deadline = time.time() + 1.0
        while time.time() < deadline:
            with lock:
                alerts = [(et, pl) for (et, pl) in events if et == "telegram_outbound_alert"]
                if len(alerts) >= 2:
                    break
            time.sleep(0.02)

        with lock:
            alerts = [(et, pl) for (et, pl) in events if et == "telegram_outbound_alert"]
            assert len(alerts) == 2

        hold.set()

    finally:
        q.stop()
