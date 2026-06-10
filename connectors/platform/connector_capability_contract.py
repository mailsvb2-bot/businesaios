from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

CANON_CONNECTOR_CAPABILITY_CONTRACT = True


class ConnectorMaturity(str, Enum):
    REAL = 'real'
    CAPABILITY_SHELL = 'capability_shell'
    PLACEHOLDER = 'placeholder'


@dataclass(frozen=True)
class ConnectorCapabilityDescriptor:
    connector_id: str
    provider: str
    version: str = 'v1'
    maturity: ConnectorMaturity = ConnectorMaturity.CAPABILITY_SHELL
    supports_read: bool = True
    supports_write: bool = False
    supports_verify: bool = False
    supports_dry_run: bool = False
    supports_idempotency: bool = False
    supports_webhooks: bool = False
    supports_oauth: bool = False
    reversible: bool = False
    requires_human_approval: bool = True
    operation_names: tuple[str, ...] = field(default_factory=tuple)
    evidence_fields: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        connector_id = str(self.connector_id or '').strip()
        provider = str(self.provider or '').strip()
        version = str(self.version or '').strip()
        if not connector_id:
            raise ValueError('connector_id is required')
        if not provider:
            raise ValueError('provider is required')
        if not version:
            raise ValueError('version is required')
        normalized_ops = tuple(sorted({str(item).strip() for item in self.operation_names if str(item).strip()}))
        normalized_evidence = tuple(sorted({str(item).strip() for item in self.evidence_fields if str(item).strip()}))
        object.__setattr__(self, 'connector_id', connector_id)
        object.__setattr__(self, 'provider', provider)
        object.__setattr__(self, 'version', version)
        object.__setattr__(self, 'operation_names', normalized_ops)
        object.__setattr__(self, 'evidence_fields', normalized_evidence)
        if self.supports_write and not self.supports_read:
            raise ValueError('write-capable connectors must also declare read support')
        if self.maturity is ConnectorMaturity.REAL and self.supports_write and not self.supports_verify:
            raise ValueError('real write connectors must expose verify support')
        if self.supports_verify and not self.operation_names:
            raise ValueError('verify-capable connectors must declare operation_names')

    def supports_operation(self, operation: str) -> bool:
        op = str(operation or '').strip()
        return bool(op) and op in set(self.operation_names)

    def allows_execution(
        self,
        *,
        operation: str,
        write: bool = False,
        verify: bool = False,
        dry_run: bool = False,
    ) -> bool:
        if not self.supports_operation(operation):
            return False
        if write and not self.supports_write:
            return False
        if verify and not self.supports_verify:
            return False
        if dry_run and not self.supports_dry_run:
            return False
        return True

    @property
    def routing_readiness(self) -> str:
        if self.maturity is ConnectorMaturity.PLACEHOLDER:
            return 'placeholder'
        if self.maturity is ConnectorMaturity.CAPABILITY_SHELL:
            return 'shell_only'
        if self.supports_write and self.supports_verify:
            return 'routable_live'
        return 'real_but_partial'

    def as_dict(self) -> dict[str, Any]:
        return {
            'connector_id': str(self.connector_id),
            'provider': str(self.provider),
            'version': str(self.version),
            'maturity': self.maturity.value,
            'supports_read': bool(self.supports_read),
            'supports_write': bool(self.supports_write),
            'supports_verify': bool(self.supports_verify),
            'supports_dry_run': bool(self.supports_dry_run),
            'supports_idempotency': bool(self.supports_idempotency),
            'supports_webhooks': bool(self.supports_webhooks),
            'supports_oauth': bool(self.supports_oauth),
            'reversible': bool(self.reversible),
            'requires_human_approval': bool(self.requires_human_approval),
            'routing_readiness': self.routing_readiness,
            'operation_names': list(self.operation_names),
            'evidence_fields': list(self.evidence_fields),
            'metadata': dict(self.metadata),
        }


__all__ = [
    'CANON_CONNECTOR_CAPABILITY_CONTRACT',
    'ConnectorCapabilityDescriptor',
    'ConnectorMaturity',
]
