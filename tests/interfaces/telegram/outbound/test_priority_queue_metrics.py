import threading

import pytest

from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue


def test_outbound_metrics_snapshot_collects_samples():
    q = TelegramOutboundQueue(
        global_rps=10_000.0,
        global_burst=10_000,
        chat_rps=10_000.0,
        chat_burst=10_000,
        max_queue=1000,
        warn_queue=900,
        emit_event=lambda et, pl: None,
        log=type('L', (), {'info': lambda *a, **k: None, 'warning': lambda *a, **k: None, 'exception': lambda *a, **k: None})(),
        overflow_policy='block',
    )

    try:
        done = threading.Event()

        def fn():
            done.set()

        ok = q.enqueue(method='sendMessage', chat_id=1, meta={}, fn=fn, critical=True, priority=q.PRIO_UX)
        assert ok is True
        assert done.wait(timeout=1.0)

        snap = q.metrics_snapshot()
        assert 'total_samples' in snap
        assert 'by_priority' in snap
        assert snap['total_samples'] >= 1

        byp = snap['by_priority']
        assert isinstance(byp, dict)
        assert len(byp) >= 1
        any_bucket = next(iter(byp.values()))
        assert 'count' in any_bucket
        assert 'wait_ms' in any_bucket
        assert 'exec_ms' in any_bucket
        assert 'p50' in any_bucket['wait_ms']
        assert 'p95' in any_bucket['wait_ms']
        assert 'p99' in any_bucket['wait_ms']

    finally:
        q.stop(timeout_s=1.0)
