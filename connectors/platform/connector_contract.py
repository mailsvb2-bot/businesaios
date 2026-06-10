from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from connectors.platform.connector_capability_contract import (
    ConnectorCapabilityDescriptor,
    ConnectorMaturity,
)
from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_maturity import ConnectorMaturity as LegacyConnectorMaturity
from interfaces.common.connector_result import ConnectorResult

CANON_PLATFORM_CONNECTOR_CONTRACT = True


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _clean_text(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text


@dataclass(frozen=True)
class ConnectorRequest:
    tenant_id: str
    connector_id: str
    operation: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    dry_run: bool = False
    trace_id: str | None = None
    timeout_seconds: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _clean_text(self.tenant_id, field_name='tenant_id')
        _clean_text(self.connector_id, field_name='connector_id')
        _clean_text(self.operation, field_name='operation')
        if self.timeout_seconds is not None and float(self.timeout_seconds) <= 0:
            raise ValueError('timeout_seconds must be > 0')

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            'tenant_id': _clean_text(self.tenant_id, field_name='tenant_id'),
            'connector_id': _clean_text(self.connector_id, field_name='connector_id'),
            'operation': _clean_text(self.operation, field_name='operation'),
            'payload': _safe_dict(self.payload),
            'idempotency_key': None if self.idempotency_key is None else str(self.idempotency_key),
            'dry_run': bool(self.dry_run),
            'trace_id': None if self.trace_id is None else str(self.trace_id),
            'timeout_seconds': None if self.timeout_seconds is None else float(self.timeout_seconds),
            'metadata': _safe_dict(self.metadata),
        }


@dataclass(frozen=True)
class ConnectorVerificationRequest:
    tenant_id: str
    connector_id: str
    operation: str
    request_payload: Mapping[str, Any] = field(default_factory=dict)
    result_payload: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _clean_text(self.tenant_id, field_name='tenant_id')
        _clean_text(self.connector_id, field_name='connector_id')
        _clean_text(self.operation, field_name='operation')

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            'tenant_id': _clean_text(self.tenant_id, field_name='tenant_id'),
            'connector_id': _clean_text(self.connector_id, field_name='connector_id'),
            'operation': _clean_text(self.operation, field_name='operation'),
            'request_payload': _safe_dict(self.request_payload),
            'result_payload': _safe_dict(self.result_payload),
            'trace_id': None if self.trace_id is None else str(self.trace_id),
            'metadata': _safe_dict(self.metadata),
        }


@runtime_checkable
class PlatformConnector(Protocol):
    connector_id: str
    provider: str

    def capabilities(self) -> ConnectorCapabilityDescriptor: ...

    def health(self) -> ConnectorHealth: ...

    def execute(self, request: ConnectorRequest) -> ConnectorResult: ...

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult: ...

    def build_snapshot(self, *, tenant_id: str) -> Mapping[str, Any]: ...


class BaseConnectorPlatformAdapter:
    """Thin adapter from existing BaseConnector surface to enterprise connector contract.

    This adapter deliberately does not add any decision logic. It only normalizes the
    already-existing connector call surface into the canonical platform contract.
    """

    def __init__(
        self,
        *,
        connector_id: str,
        provider: str,
        connector: BaseConnector,
        version: str = 'v1',
    ) -> None:
        self.connector_id = _clean_text(connector_id, field_name='connector_id')
        self.provider = _clean_text(provider, field_name='provider')
        self.version = _clean_text(version, field_name='version')
        self._connector = connector

    def capabilities(self) -> ConnectorCapabilityDescriptor:
        raw = dict(self._connector.capabilities() or {})
        metadata = raw.get('metadata') if isinstance(raw.get('metadata'), Mapping) else {}
        maturity_value = str(
            metadata.get('maturity')
            or getattr(self._connector.connector_maturity(), 'value', LegacyConnectorMaturity.PLACEHOLDER.value)
        ).strip()
        maturity = ConnectorMaturity.CAPABILITY_SHELL
        if maturity_value == LegacyConnectorMaturity.REAL.value:
            maturity = ConnectorMaturity.REAL
        elif maturity_value == LegacyConnectorMaturity.PLACEHOLDER.value:
            maturity = ConnectorMaturity.PLACEHOLDER
        operation_names = tuple(
            sorted({str(item).strip() for item in raw.get('operation_names') or () if str(item).strip()})
        )
        if not operation_names:
            operation_names = ('execute', 'verify') if bool(raw.get('verify', False)) else ('execute',)
        return ConnectorCapabilityDescriptor(
            connector_id=self.connector_id,
            provider=self.provider,
            version=self.version,
            maturity=maturity,
            supports_read=bool(raw.get('read', True)),
            supports_write=bool(raw.get('write', False)),
            supports_verify=bool(raw.get('verify', False)),
            supports_dry_run=bool(raw.get('dry_run', False)),
            supports_idempotency=bool(raw.get('idempotent', False)),
            reversible=bool(raw.get('reversible', False)),
            requires_human_approval=bool(raw.get('requires_human_approval', True)),
            operation_names=operation_names,
            evidence_fields=tuple(sorted({str(item).strip() for item in raw.get('evidence_fields') or () if str(item).strip()})),
            metadata=_safe_dict(metadata),
        )

    def health(self) -> ConnectorHealth:
        return self._connector.health()

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        request.validate()
        if _clean_text(request.connector_id, field_name='connector_id') != self.connector_id:
            raise ValueError('request.connector_id mismatch')
        return self._connector.execute(
            _clean_text(request.operation, field_name='operation'),
            _safe_dict(request.payload),
            idempotency_key=request.idempotency_key,
            dry_run=bool(request.dry_run),
        )

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        request.validate()
        if _clean_text(request.connector_id, field_name='connector_id') != self.connector_id:
            raise ValueError('request.connector_id mismatch')
        return self._connector.verify(
            _clean_text(request.operation, field_name='operation'),
            _safe_dict(request.request_payload),
            _safe_dict(request.result_payload),
        )

    def build_snapshot(self, *, tenant_id: str) -> Mapping[str, Any]:
        health = self.health()
        capabilities = self.capabilities()
        return {
            'tenant_id': _clean_text(tenant_id, field_name='tenant_id'),
            'connector_id': self.connector_id,
            'provider': self.provider,
            'version': self.version,
            'mode': str(getattr(self._connector, 'mode', 'unknown')),
            'capabilities': capabilities.as_dict(),
            'health': {
                'healthy': bool(health.healthy),
                'reason': str(health.reason or ''),
                'metadata': dict(health.metadata or {}),
            },
        }


__all__ = [
    'BaseConnectorPlatformAdapter',
    'CANON_PLATFORM_CONNECTOR_CONTRACT',
    'ConnectorRequest',
    'ConnectorVerificationRequest',
    'PlatformConnector',
]
