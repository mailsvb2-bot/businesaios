from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from security.connector_secret_scope import ConnectorSecretScope
from security.secret_contract import SecretRef

CANON_CONNECTOR_SECRET_BINDING = True


@dataclass(frozen=True)
class ConnectorSecretBinding:
    connector_id: str
    tenant_id: str
    secret_name: str
    mode: str = 'read'
    scope: str | None = None
    secret_kind: str | None = None
    secret_version: str = 'current'
    alias: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.secret_name or '').strip():
            raise ValueError('secret_name is required')
        if not str(self.mode or '').strip():
            raise ValueError('mode is required')
        if not str(self.secret_version or '').strip():
            raise ValueError('secret_version is required')
        if self.alias is not None and not str(self.alias).strip():
            raise ValueError('alias must be non-empty when provided')

    def lookup_names(self) -> tuple[str, ...]:
        self.validate()
        names = {str(self.secret_name).strip()}
        if self.alias is not None:
            names.add(str(self.alias).strip())
        return tuple(sorted(names))

    def lookup_name(self) -> str:
        return self.lookup_names()[0] if self.alias is None else str(self.alias).strip()

    def to_secret_ref(self) -> SecretRef:
        self.validate()
        return SecretRef(
            tenant_id=str(self.tenant_id).strip(),
            connector_id=str(self.connector_id).strip(),
            secret_name=str(self.secret_name).strip(),
            version=str(self.secret_version).strip(),
            scope=None if self.scope is None else str(self.scope).strip(),
        )


class ConnectorSecretBindingResolver:
    def __init__(self, *, connector_scope: ConnectorSecretScope | None = None) -> None:
        self._connector_scope = connector_scope or ConnectorSecretScope()
        self._bindings: dict[tuple[str, str, str], ConnectorSecretBinding] = {}

    def register(self, binding: ConnectorSecretBinding, *, allow_replace: bool = False) -> None:
        binding.validate()
        keys = [
            (str(binding.tenant_id).strip(), str(binding.connector_id).strip(), lookup)
            for lookup in binding.lookup_names()
        ]
        for key in keys:
            current = self._bindings.get(key)
            if current is not None and current != binding and not allow_replace:
                raise KeyError(
                    f'connector secret binding already registered: tenant={binding.tenant_id} connector={binding.connector_id} lookup={key[2]}'
                )
        for key in keys:
            self._bindings[key] = binding

    def resolve(self, *, tenant_id: str, connector_id: str, secret_name: str) -> ConnectorSecretBinding:
        key = (str(tenant_id).strip(), str(connector_id).strip(), str(secret_name or '').strip())
        if not key[2]:
            raise ValueError('secret_name is required')
        binding = self._bindings.get(key)
        if binding is None:
            raise KeyError(
                f'unknown connector secret binding: tenant={tenant_id} connector={connector_id} secret={secret_name}'
            )
        ref = binding.to_secret_ref()
        self._connector_scope.require_access(
            ref=ref,
            connector_id=str(binding.connector_id).strip(),
            mode=str(binding.mode).strip(),
            secret_kind=binding.secret_kind,
        )
        return binding

    def list_for_connector(self, *, tenant_id: str, connector_id: str) -> tuple[ConnectorSecretBinding, ...]:
        rows = {
            item
            for item in self._bindings.values()
            if str(item.tenant_id).strip() == str(tenant_id).strip() and str(item.connector_id).strip() == str(connector_id).strip()
        }
        return tuple(sorted(rows, key=lambda item: item.lookup_name()))

    def snapshot(self) -> tuple[dict[str, object], ...]:
        unique = {
            (str(item.tenant_id), str(item.connector_id), str(item.secret_name), str(item.secret_version)): item
            for item in self._bindings.values()
        }
        return tuple(
            {
                'tenant_id': str(item.tenant_id),
                'connector_id': str(item.connector_id),
                'lookup_names': list(item.lookup_names()),
                'secret_name': str(item.secret_name),
                'secret_version': str(item.secret_version),
                'mode': str(item.mode),
                'scope': None if item.scope is None else str(item.scope),
                'secret_kind': None if item.secret_kind is None else str(item.secret_kind),
                'metadata': dict(item.metadata),
            }
            for item in sorted(
                unique.values(),
                key=lambda item: (str(item.tenant_id), str(item.connector_id), item.lookup_name(), str(item.secret_version)),
            )
        )


__all__ = [
    'CANON_CONNECTOR_SECRET_BINDING',
    'ConnectorSecretBinding',
    'ConnectorSecretBindingResolver',
]
