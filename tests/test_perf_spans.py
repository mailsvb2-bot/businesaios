import tempfile


def test_span_emits_latency_event():
    from core.events.log import EventLog
    from core.observability.perf import Span
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    with tempfile.TemporaryDirectory() as td:
        path = td + "/events.db"
        with SqliteEventStore(path) as store:
            log = EventLog(store, tenant="default")
            with Span(event_log=log, stage="router", user_id="u1", correlation_key="k"):
                _ = 1 + 1
            # confirm
            evs = list(store.iter_events(tenant_id="default", start_ms=0, end_ms=None, event_type="latency_span"))
            assert len(evs) >= 1
            assert evs[-1].get("payload", {}).get("stage") == "router"
