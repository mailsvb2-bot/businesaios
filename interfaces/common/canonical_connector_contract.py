from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from interfaces.common.connector_maturity import ConnectorMaturity

CANON_CONNECTOR_OPERATIONAL_CONTRACT = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def canonical_connector_contract(
    *,
    connector_name: str,
    maturity: str,
    configured: bool,
    mode: str,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    caps = _safe_dict(capabilities)
    maturity_value = _text(maturity, default=ConnectorMaturity.PLACEHOLDER.value)
    if maturity_value not in {item.value for item in ConnectorMaturity}:
        maturity_value = ConnectorMaturity.PLACEHOLDER.value
    supports_write = bool(caps.get('write', False))
    supports_verify = bool(caps.get('verify', False))
    supports_dry_run = bool(caps.get('dry_run', False))
    requires_human_approval = bool(caps.get('requires_human_approval', True))
    routing_readiness = 'disabled'
    if maturity_value == ConnectorMaturity.PLACEHOLDER.value:
        routing_readiness = 'placeholder'
    elif configured and supports_write and supports_verify:
        routing_readiness = 'routable_live'
    elif maturity_value == ConnectorMaturity.CAPABILITY_SHELL.value:
        routing_readiness = 'shell_only'
    elif maturity_value == ConnectorMaturity.REAL.value:
        routing_readiness = 'real_but_partial'
    return {
        'connector_name': _text(connector_name),
        'maturity': maturity_value,
        'configured': bool(configured),
        'mode': _text(mode, default='stub'),
        'supports_write': supports_write,
        'supports_verify': supports_verify,
        'supports_dry_run': supports_dry_run,
        'requires_human_approval': requires_human_approval,
        'routing_readiness': routing_readiness,
        'is_real_connector': maturity_value == ConnectorMaturity.REAL.value,
        'is_capability_shell': maturity_value == ConnectorMaturity.CAPABILITY_SHELL.value,
        'is_placeholder': maturity_value == ConnectorMaturity.PLACEHOLDER.value,
    }


__all__ = ['CANON_CONNECTOR_OPERATIONAL_CONTRACT', 'canonical_connector_contract']
