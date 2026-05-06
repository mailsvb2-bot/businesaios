from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import CapabilityDiagnosticsCard
from app.web.components import DeadLetterPanel
from app.web.components import RecoveryPanel
from app.web.components import RuntimeAlertsCard
from app.web.components import SLOStatusCard
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_RUNTIME_ALERTS_PAGE = True


@dataclass(frozen=True, slots=True)
class RuntimeAlertsPage:
    runtime_alerts_card: RuntimeAlertsCard = field(default_factory=RuntimeAlertsCard)
    recovery_panel: RecoveryPanel = field(default_factory=RecoveryPanel)
    dead_letter_panel: DeadLetterPanel = field(default_factory=DeadLetterPanel)
    capability_diagnostics_card: CapabilityDiagnosticsCard = field(default_factory=CapabilityDiagnosticsCard)
    slo_status_card: SLOStatusCard = field(default_factory=SLOStatusCard)
    kind: str = 'runtime_alerts_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Runtime Alerts',
                'alerts': normalized.get('alerts'),
                'recovery': normalized.get('recovery'),
                'dead_letter': normalized.get('dead_letter'),
                'capability_diagnostics': normalized.get('capability_diagnostics'),
                'slo_status': normalized.get('slo_status'),
                'tenant_bound': True,
            },
        )

    def build_runtime_view(
        self,
        *,
        tenant_id: str,
        alerts: Iterable[Any],
        slo_definitions: Iterable[Any],
        metrics_registry: TenantMetricsRegistry,
        recovery_plan: Any | None = None,
        dead_letter_entries: Iterable[Any] = (),
        transport_results: Iterable[Any] = (),
        capability_view: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        readings = metrics_registry.snapshot(tenant_id=required_tenant_id, window_seconds=300)
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'alerts': self.runtime_alerts_card.build_from_incidents(tenant_id=required_tenant_id, alerts=alerts, limit=50),
                'recovery': None if recovery_plan is None else self.recovery_panel.build_from_plan(tenant_id=required_tenant_id, plan=recovery_plan, transport_results=transport_results),
                'dead_letter': self.dead_letter_panel.build_from_entries(tenant_id=required_tenant_id, entries=dead_letter_entries, limit=100),
                'capability_diagnostics': self.capability_diagnostics_card.build_from_capability_view(tenant_id=required_tenant_id, capability_view=capability_view),
                'slo_status': self.slo_status_card.build_from_definitions(tenant_id=required_tenant_id, definitions=slo_definitions, readings=readings),
            }
        )


__all__ = ['RuntimeAlertsPage', 'CANON_WEB_RUNTIME_ALERTS_PAGE']
