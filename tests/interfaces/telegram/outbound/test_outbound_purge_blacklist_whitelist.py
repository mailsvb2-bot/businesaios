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


def test_purge_blacklist_whitelist_keeps_payments_system_ux():
    executed = []
    lock = threading.Lock()

    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=400,
        warn_queue=350,
        emit_event=lambda et, pl: None,
        log=_log_stub(),
        overflow_policy='degrade',
        alert_drop_best_effort=True,
        alert_min_interval_s=0.01,
        self_heal_enabled=True,
        self_heal_marketing_cooldown_s=0.3,
        self_heal_on_drops=True,
        self_heal_on_sla=False,
        self_heal_on_qsize=False,
        self_heal_purge_enabled=True,
        self_heal_purge_kinds_blacklist=("marketing", "bulk", "analytics"),
        self_heal_purge_kinds_whitelist=("ux", "system", "payments", "ack"),
    )

    try:
        hold = threading.Event()
        started = threading.Event()
        pay_done = threading.Event()

        def long_ux():
            started.set()
            hold.wait(timeout=2.0)
            with lock:
                executed.append('UX_LONG_DONE')

        assert q.enqueue_ux(method='sendMessage', chat_id=1, fn=long_ux, critical=True) is True
        assert started.wait(timeout=1.0)

        # Backlog: bulk + analytics + marketing (best-effort)
        for i in range(80):
            q.enqueue_bulk(method='sendMessage', chat_id=1, fn=lambda i=i: executed.append(f'b{i}'))
            q.enqueue_analytics(method='sendMessage', chat_id=1, fn=lambda i=i: executed.append(f'a{i}'))
            q.enqueue_marketing(method='sendMessage', chat_id=1, fn=lambda i=i: executed.append(f'm{i}'))

        # Critical payments task must NOT be purged
        def pay_fn():
            with lock:
                executed.append('PAY')
            pay_done.set()

        assert q.enqueue_payments(method='sendMessage', chat_id=1, fn=pay_fn, critical=True) is True

        # Force drop -> alert -> self-heal -> purge request
        for _ in range(800):
            q.enqueue_marketing(method='sendMessage', chat_id=1, fn=lambda: None)
        q.enqueue_marketing(method='sendMessage', chat_id=1, fn=lambda: None)

        hold.set()
        assert pay_done.wait(timeout=2.0)

        time.sleep(0.25)

        with lock:
            m = [x for x in executed if isinstance(x, str) and x.startswith('m')]
            b = [x for x in executed if isinstance(x, str) and x.startswith('b')]
            a = [x for x in executed if isinstance(x, str) and x.startswith('a')]

        assert len(m) < 10, f'marketing not purged enough: {len(m)}'
        assert len(b) < 10, f'bulk not purged enough: {len(b)}'
        assert len(a) < 10, f'analytics not purged enough: {len(a)}'

    finally:
        q.stop(timeout_s=1.0)
