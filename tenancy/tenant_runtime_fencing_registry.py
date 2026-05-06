from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_RUNTIME_FENCING_REGISTRY = True


@dataclass(frozen=True)
class TenantRuntimeFencingRecord:
    tenant_id: str
    namespace: str
    current_token: int

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.namespace or '').strip():
            raise ValueError('namespace is required')
        if int(self.current_token) < 0:
            raise ValueError('current_token must be >= 0')


class TenantRuntimeFencingRegistryContract(Protocol):
    def issue(self, *, tenant_id: str, namespace: str) -> int: ...
    def current(self, *, tenant_id: str, namespace: str) -> int: ...
    def observe(self, *, tenant_id: str, namespace: str, token: int) -> int: ...
    def assert_fresh(self, *, tenant_id: str, namespace: str, token: int) -> None: ...


class InMemoryTenantRuntimeFencingRegistry(TenantRuntimeFencingRegistryContract):
    def __init__(self) -> None:
        self._values: dict[tuple[str, str], int] = {}
        self._lock = RLock()

    def issue(self, *, tenant_id: str, namespace: str) -> int:
        tid = require_tenant_id(tenant_id)
        key = (tid, self._namespace(namespace))
        with self._lock:
            next_token = int(self._values.get(key, 0)) + 1
            self._values[key] = next_token
            return next_token

    def current(self, *, tenant_id: str, namespace: str) -> int:
        tid = require_tenant_id(tenant_id)
        key = (tid, self._namespace(namespace))
        with self._lock:
            return int(self._values.get(key, 0))

    def observe(self, *, tenant_id: str, namespace: str, token: int) -> int:
        tid = require_tenant_id(tenant_id)
        numeric = int(token)
        if numeric <= 0:
            raise ValueError('token must be > 0')
        key = (tid, self._namespace(namespace))
        with self._lock:
            current = int(self._values.get(key, 0))
            if numeric > current:
                self._values[key] = numeric
                return numeric
            return current

    def assert_fresh(self, *, tenant_id: str, namespace: str, token: int) -> None:
        tid = require_tenant_id(tenant_id)
        numeric = int(token)
        if numeric <= 0:
            raise ValueError('token must be > 0')
        current = self.current(tenant_id=tid, namespace=namespace)
        if numeric != current:
            raise PermissionError(
                f'fencing token rejected: tenant={tid} namespace={namespace} token={numeric} current={current}'
            )

    @staticmethod
    def _namespace(value: str) -> str:
        text = str(value or '').strip()
        if not text:
            raise ValueError('namespace is required')
        return text


__all__ = [
    'CANON_TENANT_RUNTIME_FENCING_REGISTRY',
    'InMemoryTenantRuntimeFencingRegistry',
    'TenantRuntimeFencingRecord',
    'TenantRuntimeFencingRegistryContract',
]
