from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


CANON_TENANT_SCHEMA_VERSION_GUARD = True


class TenantSchemaVersionBackend(Protocol):
    def schema_version(self) -> int: ...


@dataclass(frozen=True)
class TenantSchemaVersionExpectation:
    component: str
    minimum_version: int
    maximum_version: int | None = None

    def validate(self) -> None:
        if not str(self.component or '').strip():
            raise ValueError('component is required')
        if int(self.minimum_version) < 0:
            raise ValueError('minimum_version must be >= 0')
        if self.maximum_version is not None and int(self.maximum_version) < int(self.minimum_version):
            raise ValueError('maximum_version must be >= minimum_version')


class TenantSchemaVersionGuard:
    def assert_compatible(self, *, backend: TenantSchemaVersionBackend, expectation: TenantSchemaVersionExpectation) -> int:
        expectation.validate()
        version = int(backend.schema_version())
        if version < int(expectation.minimum_version):
            raise RuntimeError(
                f'schema version too old for {expectation.component}: version={version} minimum={expectation.minimum_version}'
            )
        if expectation.maximum_version is not None and version > int(expectation.maximum_version):
            raise RuntimeError(
                f'schema version too new for {expectation.component}: version={version} maximum={expectation.maximum_version}'
            )
        return version


__all__ = [
    'CANON_TENANT_SCHEMA_VERSION_GUARD',
    'TenantSchemaVersionBackend',
    'TenantSchemaVersionExpectation',
    'TenantSchemaVersionGuard',
]
