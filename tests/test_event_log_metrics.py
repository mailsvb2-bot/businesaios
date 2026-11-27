from core.events.log import EventLog


class _Store(list):
    pass


def test_event_log_metrics_snapshot_counts_emit():
    log = EventLog(_Store(), tenant="t1")
    log.emit(event_type="system_error", source="test", user_id="u1", payload={})
    snap = log.metrics_snapshot()
    assert snap["emitted_total"] == 1
    assert snap["append_failures"] == 0



def test_health_status_does_not_scan_historical_tenant_events():
    from runtime.health.server import HealthSnapshot

    class IndexedEventStore:
        def __init__(self):
            self.queries = []
        def latest_event(self, *, tenant_id, event_types):
            assert tenant_id == "tenant-a"
            kind = event_types[0]
            self.queries.append(kind)
            return {"event_type": kind, "timestamp_ms": len(self.queries) * 100,
                    "payload": {"code": "temporary"}} if kind != "decision_executed" else None
        def latest_append_seq(self, *, tenant_id):
            assert tenant_id == "tenant-a"
            return 250000
        def iter_events(self, **kwargs):
            raise AssertionError("health must not scan historical events")

    store = IndexedEventStore()
    actual = HealthSnapshot(event_log=EventLog(store, tenant="tenant-a"), name="telegram").collect()
    assert actual["latest_append_seq"] == 250000
    assert "total_events" not in actual
    assert actual["telegram"]["last_poll_ms"] == 100
    assert actual["telegram"]["last_poll_error_ms"] == 200
    assert actual["ring"]["last_decision_executed_ms"] is None
    assert store.queries == ["telegram_polled", "telegram_poll_error", "decision_executed"]


def test_health_on_nonindexed_store_remains_bounded():
    from runtime.health.server import HealthSnapshot
    log = EventLog(_Store(), tenant="tenant-a")
    assert HealthSnapshot(event_log=log).collect()["latest_append_seq"] is None


def test_health_status_reads_latest_sqlite_events_for_its_own_tenant(tmp_path):
    from runtime.health.server import HealthSnapshot
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    with SqliteEventStore(str(tmp_path / "health.sqlite")) as store:
        own = EventLog(store, tenant="tenant-a")
        other = EventLog(store, tenant="tenant-b")
        own.emit(event_type="telegram_polled", source="telegram", user_id="u1",
                 payload={}, timestamp_ms=100)
        other.emit(event_type="telegram_polled", source="telegram", user_id="u2",
                   payload={}, timestamp_ms=999)
        own.emit(event_type="telegram_polled", source="telegram", user_id="u1",
                 payload={}, timestamp_ms=200)
        snapshot = HealthSnapshot(event_log=own).collect()
        assert snapshot["telegram"]["last_poll_ms"] == 200
        assert snapshot["latest_append_seq"] == 3
        assert "total_events" not in snapshot
        assert store.count_events(tenant_id="tenant-a", event_type="telegram_polled") == 2
        assert snapshot["telegram"]["last_poll_error_ms"] is None
