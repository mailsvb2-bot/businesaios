from types import SimpleNamespace

from interfaces.telegram.outbound.outbound_backpressure import put_task


class DummySlots:
    def __init__(self):
        self.acquired = 0
    def acquire(self, blocking):
        return False
    def release(self):
        self.acquired -= 1


class DummyQueue:
    def qsize(self):
        return 7


def test_put_task_drops_when_noncritical_queue_is_full():
    events = []
    obj = SimpleNamespace(
        _overflow="drop",
        _slots=DummySlots(),
        _q=DummyQueue(),
        _counters_lock=SimpleNamespace(__enter__=lambda self: None, __exit__=lambda self, exc_type, exc, tb: False),
        _dropped_best_effort=0,
        _emit=lambda event, payload: events.append((event, payload)),
        _maybe_alert=lambda: events.append(("alert", {})),
    )
    # emulate lock protocol cheaply
    class Lock:
        def __enter__(self):
            return None
        def __exit__(self, exc_type, exc, tb):
            return False
    obj._counters_lock = Lock()
    task = SimpleNamespace(method="send", priority=50, meta={"kind": "marketing"}, critical=False)
    ok = put_task(obj, (50, 1, task), task)
    assert ok is False
    assert obj._dropped_best_effort == 1
    assert events[0][0] == "telegram_outbound_dropped"
