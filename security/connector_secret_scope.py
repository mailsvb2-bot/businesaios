from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from security.secret_contract import SecretRef


CANON_CONNECTOR_SECRET_SCOPE = True


class SecretAccessOperation(str, Enum):
    READ = 'read'
    WRITE = 'write'
    ROTATE = 'rotate'
    DELETE = 'delete'


@dataclass(frozen=True)
class SecretScopeBinding:
    tenant_id: str
    connector_id: str
    allowed_secret_names: tuple[str, ...] = ()
    denied_secret_names: tuple[str, ...] = ()
    allowed_secret_prefixes: tuple[str, ...] = ()
    allowed_secret_kinds: tuple[str, ...] = ()
    allowed_operations: tuple[SecretAccessOperation, ...] = (
        SecretAccessOperation.READ,
        SecretAccessOperation.WRITE,
    )
    allow_wildcard_read: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')

    def allows(self, *, secret_name: str, mode: str, secret_kind: str | None = None) -> bool:
        normalized_mode = SecretAccessOperation(str(mode).strip().lower())
        if normalized_mode not in set(self.allowed_operations):
            return False
        if secret_name in set(self.denied_secret_names):
            return False
        if self.allowed_secret_kinds and str(secret_kind or '').strip() not in set(self.allowed_secret_kinds):
            return False
        if secret_name in set(self.allowed_secret_names):
            return True
        if any(secret_name.startswith(prefix) for prefix in self.allowed_secret_prefixes):
            return True
        if normalized_mode is SecretAccessOperation.READ and self.allow_wildcard_read:
            return True
        return False


class ConnectorSecretScope:
    def __init__(self, bindings: tuple[SecretScopeBinding, ...] = ()) -> None:
        self._bindings: dict[tuple[str, str], SecretScopeBinding] = {}
        for binding in bindings:
            self.register(binding)

    def register(self, binding: SecretScopeBinding) -> None:
        binding.validate()
        self._bindings[(binding.tenant_id, binding.connector_id)] = binding

    def require_access(
        self,
        *,
        ref: SecretRef,
        connector_id: str,
        mode: str = 'read',
        secret_kind: str | None = None,
    ) -> None:
        ref.validate()
        binding = self._bindings.get((ref.tenant_id, str(connector_id)))
        if binding is None:
            raise PermissionError(f'no secret scope for connector={connector_id}')
        if not binding.allows(secret_name=ref.secret_name, mode=mode, secret_kind=secret_kind):
            raise PermissionError(
                f'secret {ref.secret_name} mode={mode} not allowed for connector={connector_id}'
            )

    def is_allowed(
        self,
        *,
        ref: SecretRef,
        connector_id: str,
        mode: str = 'read',
        secret_kind: str | None = None,
    ) -> bool:
        try:
            self.require_access(ref=ref, connector_id=connector_id, mode=mode, secret_kind=secret_kind)
        except (PermissionError, ValueError):
            return False
        return True

    def allowed_for(self, *, tenant_id: str, connector_id: str) -> tuple[str, ...]:
        binding = self._bindings.get((tenant_id, connector_id))
        if binding is None:
            return ()
        names = set(binding.allowed_secret_names)
        names.update(binding.allowed_secret_prefixes)
        return tuple(sorted(names))


__all__ = [
    'CANON_CONNECTOR_SECRET_SCOPE',
    'ConnectorSecretScope',
    'SecretAccessOperation',
    'SecretScopeBinding',
]
