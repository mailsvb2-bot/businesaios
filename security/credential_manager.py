from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from security.connector_secret_scope import ConnectorSecretScope
from security.credential_rotation_policy import CredentialRotationPolicy, RotationDecision
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault


CANON_CREDENTIAL_MANAGER = True


@dataclass(frozen=True)
class CredentialHandle:
    ref: SecretRef
    connector_id: str
    created_at: datetime
    expires_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        self.ref.validate()
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')
        if self.created_at.tzinfo is None:
            raise ValueError('created_at must be timezone-aware')
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError('expires_at must be timezone-aware')


class CredentialManager:
    def __init__(
        self,
        *,
        vault: SecretVault,
        rotation_policy: CredentialRotationPolicy | None = None,
        connector_scope: ConnectorSecretScope | None = None,
    ) -> None:
        self._vault = vault
        self._rotation_policy = rotation_policy or CredentialRotationPolicy()
        self._connector_scope = connector_scope or ConnectorSecretScope()

    def resolve_bytes(self, handle: CredentialHandle) -> bytes:
        handle.validate()
        self._connector_scope.require_access(ref=handle.ref, connector_id=handle.connector_id, mode='read')
        record = self._vault.get_record(handle.ref)
        if hasattr(record, 'is_active') and not record.is_active():
            raise RuntimeError(f'secret {handle.ref.key()} is not active')
        return self._vault.get(handle.ref)

    def resolve_text(self, handle: CredentialHandle, *, encoding: str = 'utf-8') -> str:
        return self.resolve_bytes(handle).decode(encoding)

    def resolve(self, handle: CredentialHandle) -> str:
        return self.resolve_text(handle)

    def evaluate_rotation(
        self,
        *,
        handle: CredentialHandle,
        now: datetime,
        compromised: bool = False,
        scope_changed: bool = False,
    ) -> RotationDecision:
        handle.validate()
        return self._rotation_policy.evaluate(
            created_at=handle.created_at,
            expires_at=handle.expires_at,
            compromised=compromised,
            scope_changed=scope_changed,
            now=now,
        )


__all__ = [
    'CANON_CREDENTIAL_MANAGER',
    'CredentialHandle',
    'CredentialManager',
]
