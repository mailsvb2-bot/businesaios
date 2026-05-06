from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components import ClientOutcomeDashboardCard
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_CLIENT_OUTCOMES_PAGE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomesPage:
    dashboard_card: ClientOutcomeDashboardCard = field(default_factory=ClientOutcomeDashboardCard)
    kind: str = 'client_outcomes_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        overview = dict(normalized.get('overview') or {})
        overview['tenant_id'] = tenant_id
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Client Outcomes',
                'overview': self.dashboard_card.build(overview),
                'tenant_bound': True,
            },
        )
