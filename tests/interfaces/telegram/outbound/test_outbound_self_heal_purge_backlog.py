import threading
import time

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


def _log_stub():
    return type(
        'L',
        (),
        {
            'info': lambda *a, **k: None,
            'warning': lambda *a, **k: None,
            'exception': lambda *a, **k: None,
        },
    )()


def test_self_heal_purges_marketing_backlog_best_effort():
    executed = []
    lock = threading.Lock()

    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=300,
        warn_queue=250,
        emit_event=lambda et, pl: None,
        log=_log_stub(),
        overflow_policy='degrade',
        # alert -> self-heal on drops
        alert_drop_best_effort=True,
        alert_min_interval_s=0.01,
        self_heal_enabled=True,
        self_heal_marketing_cooldown_s=0.4,
        self_heal_on_sla=False,
        self_heal_on_qsize=False,
        self_heal_on_drops=True,
        self_heal_purge_enabled=True,
        self_heal_purge_kinds_blacklist=("marketing",),
        self_heal_purge_kinds_whitelist=("ux", "system", "payments", "ack"),
        self_heal_purge_max_items=10_000,
    )

    try:
        hold = threading.Event()
        started = threading.Event()

        def long_ux():
            started.set()
            hold.wait(timeout=2.0)
            with lock:
                executed.append('UX_LONG_DONE')

        assert q.enqueue_ux(method='sendMessage', chat_id=1, fn=long_ux, critical=True) is True
        assert started.wait(timeout=1.0)

        # Backlog: marketing tasks (best-effort)
        for i in range(150):
            def mk(i=i):
                with lock:
                    executed.append(f'm{i}')
            assert q.enqueue_marketing(method='sendMessage', chat_id=1, fn=mk) is True

        # Force a drop to trigger alert->self-heal->purge request
        # Fill queue near capacity with more marketing and then enqueue one more.
        for _ in range(400):
            q.enqueue_marketing(method='sendMessage', chat_id=1, fn=lambda: None)
        q.enqueue_marketing(method='sendMessage', chat_id=1, fn=lambda: None)

        # Release the worker so it can loop and purge before processing backlog.
        hold.set()

        # Enqueue a fresh UX task that must complete quickly.
        done = threading.Event()

        def ux2():
            with lock:
                executed.append('UX2')
            done.set()

        assert q.enqueue_ux(method='sendMessage', chat_id=1, fn=ux2, critical=True) is True
        assert done.wait(timeout=2.0)

        time.sleep(0.25)

        with lock:
            ms = [x for x in executed if isinstance(x, str) and x.startswith('m')]

        # Allow a small leak (worker could have popped 1 before purge), but backlog must NOT drain.
        assert len(ms) < 10, f'marketing backlog was not purged, executed={len(ms)}'

    finally:
        q.stop(timeout_s=1.0)
