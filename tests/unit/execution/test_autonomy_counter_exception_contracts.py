from __future__ import annotations

from pathlib import Path

import pytest

from execution.autonomy_counters import AutonomyCounterResolver, FileAutonomyCounterStore


class _CountLog:
    def __init__(self, *, hour=0, day=0, error: Exception | None = None) -> None:
        self._hour = hour
        self._day = day
        self._error = error

    def count_recent(self, *, period: str, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._hour if period == 'hour' else self._day


class _BrokenCount:
    def __int__(self) -> int:
        raise OSError('counter conversion backend unavailable')


def _resolve(event_log):
    return AutonomyCounterResolver().resolve(
        tenant_id='tenant-1',
        business_id='business-1',
        event_log=event_log,
        recent_actions=[],
        action_type='send_email',
    )


def test_corrupt_counter_json_is_tolerated(tmp_path: Path) -> None:
    store = FileAutonomyCounterStore(root_dir=tmp_path)
    store._path(tenant_id='tenant-1', business_id='business-1').write_text('{bad json', encoding='utf-8')

    assert store.load(tenant_id='tenant-1', business_id='business-1').actions_day == 0


def test_counter_file_disappearing_after_exists_check_is_tolerated(tmp_path: Path, monkeypatch) -> None:
    store = FileAutonomyCounterStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', business_id='business-1')
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError('gone')))

    assert store.load(tenant_id='tenant-1', business_id='business-1').actions_day == 0


def test_counter_storage_failure_is_visible(tmp_path: Path, monkeypatch) -> None:
    store = FileAutonomyCounterStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', business_id='business-1')
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('counter disk unavailable')))

    with pytest.raises(OSError, match='counter disk unavailable'):
        store.load(tenant_id='tenant-1', business_id='business-1')


def test_invalid_event_counts_are_tolerated() -> None:
    counters = _resolve(_CountLog(hour='bad', day=None))

    assert counters.actions_hour == 0
    assert counters.actions_day == 0


def test_event_log_backend_failure_is_visible() -> None:
    with pytest.raises(OSError, match='event log unavailable'):
        _resolve(_CountLog(error=OSError('event log unavailable')))


def test_unexpected_event_count_conversion_failure_is_visible() -> None:
    with pytest.raises(OSError, match='counter conversion backend unavailable'):
        _resolve(_CountLog(hour=_BrokenCount(), day=0))


def test_valid_event_counts_are_used() -> None:
    counters = _resolve(_CountLog(hour=3, day=8))

    assert counters.actions_hour == 3
    assert counters.actions_day == 8
