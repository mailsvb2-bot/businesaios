from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from execution.closed_loop_economic_state import apply_economic_history_to_state, safe_int
from execution.economic_export_manifest import _row_count


class _IntBackendFailure:
    def __int__(self) -> int:
        raise OSError('numeric backend unavailable')


@dataclass(frozen=True)
class _FrozenState:
    meta: dict[str, Any] = field(default_factory=dict)


class _BrokenSetterState:
    @property
    def meta(self) -> dict[str, Any]:
        return {}

    @meta.setter
    def meta(self, _value: dict[str, Any]) -> None:
        raise RuntimeError('state setter backend failure')


class _FailingRowsStore:
    path = Path('/tmp/not-used')

    def list_rows(self):
        raise OSError('economic store unavailable')


class _NonIterableRowsStore:
    def list_rows(self):
        return 42


class _FailingIterationRowsStore:
    def list_rows(self):
        def _rows():
            yield {'id': 1}
            raise OSError('economic row stream unavailable')

        return _rows()


def _apply(state: object) -> object:
    return apply_economic_history_to_state(
        world_state=state,
        economic_feedback={'event_id': 'event-1'},
        roi_history={'event_id': 'event-1'},
        policy_snapshot={'snapshot_id': 'snapshot-1'},
    )


def test_safe_int_tolerates_invalid_input() -> None:
    assert safe_int('not-an-int') is None


def test_safe_int_does_not_hide_unexpected_failure() -> None:
    with pytest.raises(OSError, match='numeric backend unavailable'):
        safe_int(_IntBackendFailure())


def test_frozen_dataclass_state_uses_replace_fallback() -> None:
    original = _FrozenState()

    updated = _apply(original)

    assert isinstance(updated, _FrozenState)
    assert updated is not original
    assert updated.meta['last_economic_feedback']['event_id'] == 'event-1'


def test_unexpected_state_setter_failure_is_visible() -> None:
    with pytest.raises(RuntimeError, match='state setter backend failure'):
        _apply(_BrokenSetterState())


def test_row_count_store_failure_is_visible() -> None:
    with pytest.raises(OSError, match='economic store unavailable'):
        _row_count(_FailingRowsStore())


def test_row_count_invalid_non_iterable_is_tolerated() -> None:
    assert _row_count(_NonIterableRowsStore()) is None


def test_row_count_iteration_failure_is_visible() -> None:
    with pytest.raises(OSError, match='economic row stream unavailable'):
        _row_count(_FailingIterationRowsStore())
