from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from reliability.lease_fencing_token import LeaseFencingToken


@dataclass
class FakeEffectStore:
    latest_token: LeaseFencingToken | None = None
    writes: list[str] = field(default_factory=list)

    def write(self, *, token: LeaseFencingToken, payload: str) -> None:
        if self.latest_token is not None and token.is_stale_against(current=self.latest_token):
            raise PermissionError('stale writer rejected by fencing token')
        self.latest_token = token
        self.writes.append(payload)


def test_stale_writer_is_rejected_by_fencing_token() -> None:
    store = FakeEffectStore()
    store.write(token=LeaseFencingToken(2), payload='new leader write')
    with pytest.raises(PermissionError):
        store.write(token=LeaseFencingToken(1), payload='stale writer write')
    assert store.writes == ['new leader write']


def test_equal_token_retry_is_allowed_for_idempotent_replay() -> None:
    store = FakeEffectStore()
    store.write(token=LeaseFencingToken(3), payload='first')
    store.write(token=LeaseFencingToken(3), payload='same-token retry')
    assert store.writes == ['first', 'same-token retry']


def test_newer_token_is_allowed() -> None:
    store = FakeEffectStore()
    store.write(token=LeaseFencingToken(3), payload='old leader')
    store.write(token=LeaseFencingToken(4), payload='new leader')
    assert store.writes == ['old leader', 'new leader']
