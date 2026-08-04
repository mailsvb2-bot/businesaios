from __future__ import annotations

import pytest

from execution.blast_radius_guard import BlastRadiusGuard


class _CountLog:
    def __init__(self, value=None, error: Exception | None = None) -> None:
        self._value = value
        self._error = error

    def count_recent(self, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._value


class _QueryLog:
    def __init__(self, rows=None, error: Exception | None = None) -> None:
        self._rows = rows
        self._error = error

    def query_recent(self, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._rows


class _BrokenCount:
    def __int__(self) -> int:
        raise OSError('counter backend unavailable')


def _count(event_log) -> int:
    return BlastRadiusGuard._event_log_count(
        event_log=event_log,
        tenant_id='tenant-1',
        action_type='send_email',
        period='hour',
    )


def test_invalid_count_value_is_tolerated() -> None:
    assert _count(_CountLog(value='not-an-int')) == 0


def test_count_backend_failure_is_visible() -> None:
    with pytest.raises(OSError, match='event log unavailable'):
        _count(_CountLog(error=OSError('event log unavailable')))


def test_unexpected_count_conversion_failure_is_visible() -> None:
    with pytest.raises(OSError, match='counter backend unavailable'):
        _count(_CountLog(value=_BrokenCount()))


def test_query_rows_are_counted() -> None:
    assert _count(_QueryLog(rows=({'id': 1}, {'id': 2}))) == 2


def test_query_backend_failure_is_visible() -> None:
    with pytest.raises(OSError, match='event query unavailable'):
        _count(_QueryLog(error=OSError('event query unavailable')))


def test_query_non_iterable_value_is_tolerated() -> None:
    assert _count(_QueryLog(rows=42)) == 0


def test_query_iteration_failure_is_visible() -> None:
    def _rows():
        yield {'id': 1}
        raise OSError('event stream unavailable')

    with pytest.raises(OSError, match='event stream unavailable'):
        _count(_QueryLog(rows=_rows()))
