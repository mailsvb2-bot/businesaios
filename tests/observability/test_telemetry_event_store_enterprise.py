from __future__ import annotations

from observability.platform.telemetry.event_store import JsonlEventStore, SqliteEventStore, build_default_event_store


def test_jsonl_event_store_skips_corrupted_lines_and_filters_time(tmp_path) -> None:
    path = tmp_path / 'events.jsonl'
    store = JsonlEventStore(path)
    store.append(tenant_id='tenant-1', user_id='u1', event_type='a', payload={'v': 1})
    with path.open('a', encoding='utf-8') as fh:
        fh.write('{bad json}\n')
    store.append(tenant_id='tenant-1', user_id='u1', event_type='b', payload={'v': 2})
    latest = list(store.latest_events(tenant_id='tenant-1', limit=10))
    assert len(latest) == 2
    all_events = list(store.iter_events(tenant_id='tenant-1', start_ms=0, end_ms=9999999999999))
    assert len(all_events) == 2




def test_sqlite_event_store_latest_events_returns_most_recent_first(tmp_path) -> None:
    store = SqliteEventStore(tmp_path / 'events.sqlite3')
    store.append(tenant_id='tenant-a', user_id='u1', event_type='evt', payload={'n': 1})
    store.append(tenant_id='tenant-a', user_id='u1', event_type='evt', payload={'n': 2})
    latest = list(store.latest_events(tenant_id='tenant-a', user_id='u1', event_type='evt', limit=1))
    assert latest[0]['payload']['n'] == 2


def test_build_default_event_store_prefers_sqlite_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_TELEMETRY_EVENT_STORE_BACKEND', 'sqlite')
    store = build_default_event_store(path=tmp_path / 'events.sqlite3')
    assert isinstance(store, SqliteEventStore)
