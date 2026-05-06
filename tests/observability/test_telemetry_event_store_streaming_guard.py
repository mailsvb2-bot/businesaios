from __future__ import annotations

from pathlib import Path

from observability.platform.telemetry.event_store import JsonlEventStore


def test_jsonl_event_store_tolerates_corrupt_lines_without_read_text(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / 'events.jsonl'
    path.write_text('{"tenant_id":"t1","event_type":"ok","user_id":null,"payload":{},"ts_iso":"2026-01-01T00:00:00+00:00"}\n{bad json\n', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda self, *args, **kwargs: (_ for _ in ()).throw(AssertionError('read_text should not be used')))
    store = JsonlEventStore(path)
    events = list(store.iter_events(tenant_id='t1'))
    assert len(events) == 1
    assert events[0]['event_type'] == 'ok'
