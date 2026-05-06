from __future__ import annotations

import pytest

from runtime.boot.outbound_constructor import build_with_supported_kwargs


class _ModernQueue:
    def __init__(self, *, max_queue: int, alert_qsize: int, self_heal_enabled: bool) -> None:
        self.values = (max_queue, alert_qsize, self_heal_enabled)


class _LegacyQueue:
    def __init__(self, *, max_queue: int) -> None:
        self.values = (max_queue,)


class _BrokenQueue:
    def __init__(self, *, max_queue: int, alert_qsize: int) -> None:
        raise TypeError('internal queue bug must not be masked')


def test_build_with_supported_kwargs_preserves_supported_constructor_surface() -> None:
    modern = build_with_supported_kwargs(constructor=_ModernQueue, kwargs={'max_queue': 10, 'alert_qsize': 5, 'self_heal_enabled': True})
    legacy = build_with_supported_kwargs(constructor=_LegacyQueue, kwargs={'max_queue': 10, 'alert_qsize': 5, 'self_heal_enabled': True})
    assert modern.values == (10, 5, True)
    assert legacy.values == (10,)


def test_build_with_supported_kwargs_does_not_hide_internal_type_errors() -> None:
    with pytest.raises(TypeError, match='internal queue bug must not be masked'):
        build_with_supported_kwargs(constructor=_BrokenQueue, kwargs={'max_queue': 10, 'alert_qsize': 5})
