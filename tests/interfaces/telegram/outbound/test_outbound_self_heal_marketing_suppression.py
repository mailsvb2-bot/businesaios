import time

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


def test_self_heal_suppresses_marketing_after_alert_then_recovers():
    # Trigger an alert via best-effort drop (queue full),
    # and self-heal is configured to react to drops.
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1,
        warn_queue=1,
        emit_event=None,
        log=type("_L", (), {"warning": lambda *a, **k: None})(),
        overflow_policy="drop",
        auto_start_on_use=False,
        alert_ux_wait_p95_ms=0.0,
        alert_drop_best_effort=True,
        alert_qsize=0,
        alert_min_interval_s=0.01,  # fast for test
        metrics_logger=lambda s: None,
        self_heal_enabled=True,
        self_heal_marketing_cooldown_s=0.3,
        self_heal_on_sla=False,
        self_heal_on_qsize=False,
        self_heal_on_drops=True,
    )

    try:
        # Fill queue with one UX task so queue becomes full (worker not started yet).

        ok = q.enqueue_ux(method="sendMessage", chat_id=1, fn=lambda: None, critical=True)
        assert ok is True

        # Now marketing will drop (full) -> alert -> self-heal kicks in.
        ok2 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok2 is False

        # Start worker now and let it drain the UX task.
        q.start()
        # Allow a tiny moment for the worker to start and drain.
        time.sleep(0.05)

        # Even if queue is now free, marketing should be suppressed during cooldown.
        assert q.is_marketing_suppressed() is True
        ok3 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok3 is False

        # After cooldown, marketing should be allowed again (queue should accept).
        time.sleep(0.35)
        assert q.is_marketing_suppressed() is False
        ok4 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok4 is True

    finally:
        q.stop()
