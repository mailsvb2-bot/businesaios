import threading

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


class _NullLog:
    def info(self, *a, **k):
        return None

    def warning(self, *a, **k):
        return None

    def exception(self, *a, **k):
        return None


def test_priorityqueue_fifo_within_same_priority():
    """Canonical invariant:
    - For tasks with the same priority, execution order must be FIFO.

    This validates that `seq` is used in the priority queue key.
    """
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
    q.start()

    try:
        executed: list[int] = []
        lock = threading.Lock()
        done = threading.Event()

        n = 50

        def mk_fn(i: int):
            def _fn():
                with lock:
                    executed.append(i)
                    if len(executed) >= n:
                        done.set()

            return _fn

        # Enqueue many NORMAL-priority tasks in increasing order.
        for i in range(n):
            ok = q.enqueue(
                method="sendMessage",
                chat_id=123,
                meta={"i": i},
                fn=mk_fn(i),
                priority=q.PRIO_NORMAL,  # same priority
                critical=True,
            )
            assert ok is True

        assert done.wait(timeout=2.0), "Not all tasks executed in time"

        with lock:
            assert executed == list(range(n)), f"Expected FIFO order, got: {executed[:10]}..."

    finally:
        q.stop()
