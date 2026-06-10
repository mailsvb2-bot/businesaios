from __future__ import annotations

"""Tenant policy override card.

Shows already-existing override state only.
No policy evaluation, no permission grant logic, no decision path.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_POLICY_OVERRIDE_CARD = True


def _enum_values(values: Any) -> tuple[str, ...]:
    return tuple(sorted(str(getattr(item, 'value', item) or '').strip() for item in tuple(values or ()) if str(getattr(item, 'value', item) or '').strip()))


@dataclass(frozen=True, slots=True)
class PolicyOverrideCard:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'policy_override_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        override = dict(normalized.get('override', {}) or {})
        override_tenant_id = normalize_tenant_id(override.get('tenant_id'))
        if override_tenant_id and override_tenant_id != tenant_id:
            override = {}
        if override:
            override['tenant_id'] = tenant_id
        result = {
            'tenant_id': tenant_id,
            'has_override': bool(normalized.get('has_override')) and bool(override),
            'override': override,
            'summary': {
                'added_permission_count': len(tuple(override.get('add_permissions', ()) or ())),
                'removed_permission_count': len(tuple(override.get('remove_permissions', ()) or ())),
                'blocked_action_count': len(tuple(override.get('blocked_action_names', ()) or ())),
                'forced_approval_category_count': len(tuple(override.get('force_approval_for_categories', ()) or ())),
            },
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_override(self, *, tenant_id: str, override: Any | None) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        if override is None:
            return self.build({'tenant_id': required_tenant_id, 'has_override': False, 'override': {}})
        override_tenant_id = normalize_tenant_id(getattr(override, 'tenant_id', ''))
        if override_tenant_id and override_tenant_id != required_tenant_id:
            return self.build({'tenant_id': required_tenant_id, 'has_override': False, 'override': {}})
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'has_override': True,
                'override': {
                    'tenant_id': required_tenant_id,
                    'add_permissions': _enum_values(getattr(override, 'add_permissions', ())),
                    'remove_permissions': _enum_values(getattr(override, 'remove_permissions', ())),
                    'blocked_action_names': tuple(sorted(str(x).strip() for x in tuple(getattr(override, 'blocked_action_names', ()) or ()) if str(x).strip())),
                    'blocked_categories': tuple(sorted(str(x).strip() for x in tuple(getattr(override, 'blocked_categories', ()) or ()) if str(x).strip())),
                    'force_approval_for_categories': tuple(sorted(str(x).strip() for x in tuple(getattr(override, 'force_approval_for_categories', ()) or ()) if str(x).strip())),
                    'metadata': dict(getattr(override, 'metadata', {}) or {}),
                },
            }
        )


__all__ = ['PolicyOverrideCard', 'CANON_WEB_POLICY_OVERRIDE_CARD']
