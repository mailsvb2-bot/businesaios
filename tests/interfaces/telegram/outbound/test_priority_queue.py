import threading
import time

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


class _NullLog:
    def info(self, *a, **k):
        return None

    def warning(self, *a, **k):
        return None

    def exception(self, *a, **k):
        return None


def test_priorityqueue_ux_preempts_marketing_backlog():
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=5000,
        warn_queue=4500,
        emit_event=lambda et, pl: None,
        log=_NullLog(),
        overflow_policy="block",
    )
    q.start()

    try:
        executed = []
        lock = threading.Lock()

        marketing_n = 200

        def mk_marketing(i: int):
            def _fn():
                time.sleep(0.01)
                with lock:
                    executed.append(f"m{i}")
            return _fn

        for i in range(marketing_n):
            ok = q.enqueue_marketing(method="sendMessage", chat_id=123, fn=mk_marketing(i))
            assert ok is True

        time.sleep(0.05)

        ux_done = threading.Event()

        def ux_fn():
            with lock:
                executed.append("UX")
            ux_done.set()

        ok = q.enqueue_ux(method="sendMessage", chat_id=123, fn=ux_fn, meta={"kind": "ux"}, critical=True)
        assert ok is True

        assert ux_done.wait(timeout=0.5), "UX task did not execute promptly under marketing backlog"

        with lock:
            ux_index = executed.index("UX")
            marketing_done_so_far = sum(1 for x in executed if x.startswith("m"))

        assert marketing_done_so_far < marketing_n, "Marketing backlog drained before UX executed (no preemption)"
        assert ux_index < 80, f"UX executed too late in order: ux_index={ux_index}"

    finally:
        q.stop()


def test_priorityqueue_marketing_is_best_effort_and_drops_on_full():
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1,
        warn_queue=1,
        emit_event=lambda et, pl: None,
        log=_NullLog(),
        overflow_policy="degrade",
        auto_start_on_use=False,
    )
    q.start()

    try:
        ok1 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok1 is True
        ok2 = q.enqueue_marketing(method="sendMessage", chat_id=1, fn=lambda: None)
        assert ok2 is False

    finally:
        q.stop()


import pytest

from interfaces.telegram.outbound.outbound_queue import OutboundTask


def test_priorityqueue_legacy_enqueue_methods_preserve_priority_behavior() -> None:
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1000,
        warn_queue=900,
        emit_event=lambda et, pl: None,
        log=_NullLog(),
        overflow_policy="block",
    )

    try:
        executed: list[str] = []
        lock = threading.Lock()
        done = threading.Event()

        def mk(name: str):
            def _fn() -> None:
                with lock:
                    executed.append(name)
                    if len(executed) >= 3:
                        done.set()
            return _fn

        with pytest.warns(DeprecationWarning):
            assert q.enqueue_normal(OutboundTask(
                priority=q.PRIO_NORMAL,
                seq=0,
                enqueue_t_ns=0,
                method='sendMessage',
                chat_id=1,
                fn=mk('N1'),
                created_at=0.0,
                meta={},
                critical=True,
            )) is True

            assert q.enqueue_high(OutboundTask(
                priority=q.PRIO_UX,
                seq=0,
                enqueue_t_ns=0,
                method='sendMessage',
                chat_id=1,
                fn=mk('UX'),
                created_at=0.0,
                meta={},
                critical=True,
            )) is True

            assert q.enqueue_normal(OutboundTask(
                priority=q.PRIO_NORMAL,
                seq=0,
                enqueue_t_ns=0,
                method='sendMessage',
                chat_id=1,
                fn=mk('N2'),
                created_at=0.0,
                meta={},
                critical=True,
            )) is True

        assert done.wait(timeout=2.0)

        with lock:
            assert 'UX' in executed
            assert executed.index('UX') < executed.index('N2')

    finally:
        q.stop(timeout_s=1.0)
