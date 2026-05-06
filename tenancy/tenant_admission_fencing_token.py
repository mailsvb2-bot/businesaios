from __future__ import annotations

from dataclasses import dataclass


CANON_TENANT_ADMISSION_FENCING_TOKEN = True


@dataclass(frozen=True, order=True)
class TenantAdmissionFencingToken:
    value: int

    def __post_init__(self) -> None:
        if int(self.value) <= 0:
            raise ValueError('tenant admission fencing token must be > 0')

    @classmethod
    def parse(cls, value: int | str) -> 'TenantAdmissionFencingToken':
        return cls(int(value))

    def as_int(self) -> int:
        return int(self.value)

    def assert_not_stale_against(self, *, current: 'TenantAdmissionFencingToken') -> None:
        if int(self.value) < int(current.value):
            raise PermissionError(
                f'stale tenant admission fencing token: candidate={self.value} current={current.value}'
            )


__all__ = [
    'CANON_TENANT_ADMISSION_FENCING_TOKEN',
    'TenantAdmissionFencingToken',
]
