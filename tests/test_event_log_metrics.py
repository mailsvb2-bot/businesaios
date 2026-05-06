from core.events.log import EventLog


class _Store(list):
    pass


def test_event_log_metrics_snapshot_counts_emit():
    log = EventLog(_Store(), tenant="t1")
    log.emit(event_type="system_error", source="test", user_id="u1", payload={})
    snap = log.metrics_snapshot()
    assert snap["emitted_total"] == 1
    assert snap["append_failures"] == 0
