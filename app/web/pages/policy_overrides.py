from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components import PolicyOverrideCard
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_POLICY_OVERRIDES_PAGE = True


@dataclass(frozen=True, slots=True)
class PolicyOverridesPage:
    policy_override_card: PolicyOverrideCard = field(default_factory=PolicyOverrideCard)
    kind: str = 'policy_overrides_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Policy Overrides',
                'override_card': normalized.get('override_card'),
                'tenant_bound': True,
            },
        )

    def build_from_override(self, *, tenant_id: str, override: Any | None) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        return self.build({'tenant_id': required_tenant_id, 'override_card': self.policy_override_card.build_from_override(tenant_id=required_tenant_id, override=override)})


__all__ = ['PolicyOverridesPage', 'CANON_WEB_POLICY_OVERRIDES_PAGE']
