from __future__ import annotations

"""Admin/operator console aggregate page.

Thin composition only. It assembles already-built cards from canonical stores.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import AnalyticsDashboardCard
from app.web.components import ApprovalQueueCard
from app.web.components import AutonomyBudgetPanel
from app.web.components import CapabilityDiagnosticsCard
from app.web.components import DeadLetterPanel
from app.web.components import ExecutionTraceCard
from app.web.components import MonetizationDashboardCard
from app.web.components import PolicyOverrideCard
from app.web.components import RevenueAdvisoryCard
from app.web.components import ClientOutcomeDashboardCard
from app.web.components import QuotaUsageCard
from app.web.components import RecoveryPanel
from app.web.components import RunControlPanel
from app.web.components import RuntimeAlertsCard
from app.web.components import SecurityEventsCard
from app.web.components import SLOStatusCard
from app.web.components import TenantSelector
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_ADMIN_PAGE = True


@dataclass(frozen=True, slots=True)
class AdminPage:
    tenant_selector: TenantSelector = field(default_factory=TenantSelector)
    analytics_dashboard_card: AnalyticsDashboardCard = field(default_factory=AnalyticsDashboardCard)
    approval_queue_card: ApprovalQueueCard = field(default_factory=ApprovalQueueCard)
    monetization_dashboard_card: MonetizationDashboardCard = field(default_factory=MonetizationDashboardCard)
    revenue_advisory_card: RevenueAdvisoryCard = field(default_factory=RevenueAdvisoryCard)
    client_outcome_dashboard_card: ClientOutcomeDashboardCard = field(default_factory=ClientOutcomeDashboardCard)
    runtime_alerts_card: RuntimeAlertsCard = field(default_factory=RuntimeAlertsCard)
    policy_override_card: PolicyOverrideCard = field(default_factory=PolicyOverrideCard)
    run_control_panel: RunControlPanel = field(default_factory=RunControlPanel)
    execution_trace_card: ExecutionTraceCard = field(default_factory=ExecutionTraceCard)
    security_events_card: SecurityEventsCard = field(default_factory=SecurityEventsCard)
    dead_letter_panel: DeadLetterPanel = field(default_factory=DeadLetterPanel)
    quota_usage_card: QuotaUsageCard = field(default_factory=QuotaUsageCard)
    autonomy_budget_panel: AutonomyBudgetPanel = field(default_factory=AutonomyBudgetPanel)
    capability_diagnostics_card: CapabilityDiagnosticsCard = field(default_factory=CapabilityDiagnosticsCard)
    recovery_panel: RecoveryPanel = field(default_factory=RecoveryPanel)
    slo_status_card: SLOStatusCard = field(default_factory=SLOStatusCard)
    kind: str = 'admin_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        sections = {
            'tenant_selector': normalized.get('tenant_selector'),
            'analytics_overview': normalized.get('analytics_overview'),
            'monetization_overview': normalized.get('monetization_overview'),
            'revenue_advisory': normalized.get('revenue_advisory'),
            'approval_queue': normalized.get('approval_queue'),
            'runtime_alerts': normalized.get('runtime_alerts'),
            'client_outcomes': normalized.get('client_outcomes'),
            'policy_override': normalized.get('policy_override'),
            'run_control': normalized.get('run_control'),
            'execution_trace': normalized.get('execution_trace'),
            'security_events': normalized.get('security_events'),
            'dead_letter': normalized.get('dead_letter'),
            'quota_usage': normalized.get('quota_usage'),
            'autonomy_budget': normalized.get('autonomy_budget'),
            'capability_diagnostics': normalized.get('capability_diagnostics'),
            'recovery': normalized.get('recovery'),
            'slo_status': normalized.get('slo_status'),
            'platform_control_center': normalized.get('platform_control_center'),
        }
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Admin / Operator Console',
                'sections': sections,
                'section_count': sum(1 for value in sections.values() if value is not None),
                'tenant_bound': True,
                'quick_actions': ({'label': 'Открыть индивидуальную админку', 'path': '/web/platform-admin'},),
            },
        )

    def build_dashboard(
        self,
        *,
        tenant_id: str,
        tenant_records: Iterable[Any],
        approvals: Iterable[Any],
        runtime_alerts: Iterable[Any],
        override: Any | None,
        trace_events: Iterable[Any],
        security_events: Iterable[Any],
        quota_usage: Mapping[str, Any],
        quota_limits: Mapping[str, Any],
        slo_definitions: Iterable[Any],
        metrics_registry: TenantMetricsRegistry,
        run_snapshot: Any | None = None,
        allowed_controls: Iterable[Any] = (),
        recovery_plan: Any | None = None,
        dead_letter_entries: Iterable[Any] = (),
        budget_usage: Any | None = None,
        budget_verdict: Any | None = None,
        transport_results: Iterable[Any] = (),
        capability_view: Mapping[str, Any] | None = None,
        analytics_bundle: Mapping[str, Any] | None = None,
        monetization_snapshot: Mapping[str, Any] | None = None,
        revenue_advisory: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        readings = metrics_registry.snapshot(tenant_id=required_tenant_id, window_seconds=300)
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'tenant_selector': self.tenant_selector.build_from_registry(selected_tenant_id=required_tenant_id, tenant_records=tenant_records),
                'analytics_overview': None if analytics_bundle is None else self.analytics_dashboard_card.build(analytics_bundle.get('dashboard')),
                'monetization_overview': None if monetization_snapshot is None else self.monetization_dashboard_card.build(monetization_snapshot),
                'revenue_advisory': None if revenue_advisory is None else self.revenue_advisory_card.build(revenue_advisory),
                'approval_queue': self.approval_queue_card.build_from_records(tenant_id=required_tenant_id, records=approvals, limit=10),
                'runtime_alerts': self.runtime_alerts_card.build_from_incidents(tenant_id=required_tenant_id, alerts=runtime_alerts, limit=10),
                'client_outcomes': None if monetization_snapshot is None else self.client_outcome_dashboard_card.build({'tenant_id': required_tenant_id, 'gross_revenue': monetization_snapshot.get('gross_revenue_minor', 0) / 100 if isinstance(monetization_snapshot.get('gross_revenue_minor'), int) else monetization_snapshot.get('gross_revenue_minor', 0), 'net_revenue': monetization_snapshot.get('net_revenue_minor', 0) / 100 if isinstance(monetization_snapshot.get('net_revenue_minor'), int) else monetization_snapshot.get('net_revenue_minor', 0), 'currency': monetization_snapshot.get('currency', 'USD')}),
                'policy_override': self.policy_override_card.build_from_override(tenant_id=required_tenant_id, override=override),
                'run_control': None if run_snapshot is None else self.run_control_panel.build_from_snapshot(tenant_id=required_tenant_id, run_snapshot=run_snapshot, allowed_controls=allowed_controls, recent_events=trace_events, recovery_plan=recovery_plan),
                'execution_trace': self.execution_trace_card.build_from_events(tenant_id=required_tenant_id, events=trace_events, limit=25),
                'security_events': self.security_events_card.build_from_events(tenant_id=required_tenant_id, events=security_events, limit=10),
                'dead_letter': self.dead_letter_panel.build_from_entries(tenant_id=required_tenant_id, entries=dead_letter_entries, limit=100),
                'quota_usage': self.quota_usage_card.build_from_snapshot(tenant_id=required_tenant_id, usage=quota_usage, limits=quota_limits),
                'autonomy_budget': None if budget_usage is None or budget_verdict is None else self.autonomy_budget_panel.build_from_verdict(tenant_id=required_tenant_id, usage=budget_usage, verdict=budget_verdict),
                'capability_diagnostics': self.capability_diagnostics_card.build_from_capability_view(tenant_id=required_tenant_id, capability_view=capability_view),
                'recovery': None if recovery_plan is None else self.recovery_panel.build_from_plan(tenant_id=required_tenant_id, plan=recovery_plan, transport_results=transport_results),
                'slo_status': self.slo_status_card.build_from_definitions(tenant_id=required_tenant_id, definitions=slo_definitions, readings=readings),
            }
        )


__all__ = ['AdminPage', 'CANON_WEB_ADMIN_PAGE']
