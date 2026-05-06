from __future__ import annotations

from dataclasses import dataclass

CANON_LEASE_FENCING_TOKEN = True

@dataclass(frozen=True, order=True)
class LeaseFencingToken:
    value: int
    def __post_init__(self) -> None:
        if int(self.value) <= 0:
            raise ValueError('fencing token must be > 0')
    @classmethod
    def parse(cls, value: int | str) -> 'LeaseFencingToken':
        return cls(int(value))
    def as_int(self) -> int:
        return int(self.value)
    def is_stale_against(self, *, current: 'LeaseFencingToken') -> bool:
        return int(self.value) < int(current.value)
    def assert_not_stale_against(self, *, current: 'LeaseFencingToken') -> None:
        if self.is_stale_against(current=current):
            raise PermissionError(f'stale fencing token: candidate={self.value} current={current.value}')

def assert_fencing_token_progression(*, current: LeaseFencingToken | None, candidate: LeaseFencingToken) -> None:
    if current is None:
        return
    candidate.assert_not_stale_against(current=current)
