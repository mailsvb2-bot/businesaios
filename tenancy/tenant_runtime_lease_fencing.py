from __future__ import annotations

from dataclasses import dataclass


CANON_TENANT_RUNTIME_LEASE_FENCING = True


@dataclass(frozen=True, order=True)
class TenantRuntimeLeaseFencingToken:
    value: int

    def __post_init__(self) -> None:
        if int(self.value) <= 0:
            raise ValueError('fencing token must be > 0')

    @classmethod
    def parse(cls, value: int | str) -> 'TenantRuntimeLeaseFencingToken':
        return cls(int(value))

    def as_int(self) -> int:
        return int(self.value)

    def is_stale_against(self, *, current: 'TenantRuntimeLeaseFencingToken') -> bool:
        return int(self.value) < int(current.value)

    def assert_not_stale_against(self, *, current: 'TenantRuntimeLeaseFencingToken') -> None:
        if self.is_stale_against(current=current):
            raise PermissionError(
                f'stale tenant runtime fencing token: candidate={self.value} current={current.value}'
            )


def assert_runtime_fencing_progression(
    *,
    current: TenantRuntimeLeaseFencingToken | None,
    candidate: TenantRuntimeLeaseFencingToken,
) -> None:
    if current is None:
        return
    candidate.assert_not_stale_against(current=current)


__all__ = [
    'CANON_TENANT_RUNTIME_LEASE_FENCING',
    'TenantRuntimeLeaseFencingToken',
    'assert_runtime_fencing_progression',
]
