from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from shared.kinded_payloads import build_kinded_payload
from application.capability.capability_operator_view import normalize_capability_view


CANON_WEB_CAPABILITY_DIAGNOSTICS_CARD = True


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return ()


@dataclass(frozen=True, slots=True)
class CapabilityDiagnosticsCard:
    kind: str = 'capability_diagnostics_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        diagnostics = _safe_dict(normalized.get('diagnostics'))
        signals = tuple(
            {
                'code': str(_safe_dict(item).get('code') or '').strip(),
                'severity': str(_safe_dict(item).get('severity') or 'info').strip() or 'info',
                'summary': str(_safe_dict(item).get('summary') or '').strip(),
                'operator_actionable': bool(_safe_dict(item).get('operator_actionable', False)),
                'metadata': _safe_dict(_safe_dict(item).get('metadata')),
            }
            for item in _safe_tuple(diagnostics.get('signals'))
            if str(_safe_dict(item).get('code') or '').strip()
        )
        severity_rank = {'critical': 4, 'high': 3, 'medium': 2, 'warning': 2, 'info': 1}
        sorted_signals = tuple(sorted(signals, key=lambda row: (severity_rank.get(str(row.get('severity') or 'info').lower(), 0), str(row.get('code') or '')), reverse=True))
        operator_action = str(diagnostics.get('operator_action') or '').strip() or 'none'
        result = {
            'tenant_id': tenant_id,
            'status': str(diagnostics.get('status') or '').strip() or 'unknown',
            'headline': str(diagnostics.get('headline') or '').strip() or 'Capability diagnostics unavailable.',
            'operator_action': operator_action,
            'signals': sorted_signals,
            'signal_count': len(sorted_signals),
            'operator_action_required': operator_action not in {'', 'none'},
            'summary': {
                'critical_count': sum(1 for item in sorted_signals if str(item.get('severity') or '').lower() == 'critical'),
                'high_count': sum(1 for item in sorted_signals if str(item.get('severity') or '').lower() == 'high'),
                'operator_actionable_count': sum(1 for item in sorted_signals if bool(item.get('operator_actionable'))),
            },
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, result)

    def build_from_capability_view(self, *, tenant_id: str, capability_view: Mapping[str, Any] | None) -> dict[str, Any] | None:
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_view = normalize_capability_view(capability_view)
        diagnostics = _safe_dict(normalized_view.get('diagnostics'))
        diagnostics_tenant_id = normalize_tenant_id(normalized_view.get('tenant_id'))
        if diagnostics_tenant_id and diagnostics_tenant_id != normalized_tenant_id:
            return None
        if not diagnostics:
            return None
        return self.build({'tenant_id': normalized_tenant_id, 'diagnostics': diagnostics})


__all__ = ['CapabilityDiagnosticsCard', 'CANON_WEB_CAPABILITY_DIAGNOSTICS_CARD']
