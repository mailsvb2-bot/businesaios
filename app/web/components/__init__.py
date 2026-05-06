from __future__ import annotations

"""Canonical web components package surface with explicit owner exports.

The historical ``public_api`` import path is now installed directly by the
package owner instead of a dedicated compat package directory.
"""

from typing import Final

from runtime.public_api_alias import install_public_api_alias

from app.web.components.approval_queue_card import ApprovalQueueCard
from app.web.components.analytics_dashboard_card import AnalyticsDashboardCard
from app.web.components.analytics_explainability_card import AnalyticsExplainabilityCard
from app.web.components.analytics_rollup_card import AnalyticsRollupCard
from app.web.components.audit_log_table import AuditLogTable
from app.web.components.autonomy_budget_panel import AutonomyBudgetPanel
from app.web.components.capability_diagnostics_card import CapabilityDiagnosticsCard
from app.web.components.dead_letter_panel import DeadLetterPanel
from app.web.components.execution_trace_card import ExecutionTraceCard
from app.web.components.capacity_budget_panel import CapacityBudgetPanel
from app.web.components.escalation_history_panel import EscalationHistoryPanel
from app.web.components.inference_queue_pressure_panel import InferenceQueuePressurePanel
from app.web.components.inference_tier_panel import InferenceTierPanel
from app.web.components.inference_verification_panel import InferenceVerificationPanel
from app.web.components.manual_capacity_override_panel import ManualCapacityOverridePanel
from app.web.components.provider_health_panel import InferenceProviderHealthPanel
from app.web.components.provider_mix_panel import ProviderMixPanel
from app.web.components.monetization_dashboard_card import MonetizationDashboardCard
from app.web.components.revenue_advisory_card import RevenueAdvisoryCard
from app.web.components.client_outcome_dashboard_card import ClientOutcomeDashboardCard
from app.web.components.policy_override_card import PolicyOverrideCard
from app.web.components.queue_alert_history_card import QueueAlertHistoryCard
from app.web.components.queue_health_card import QueueHealthCard
from app.web.components.queue_remediation_analytics_card import QueueRemediationAnalyticsCard
from app.web.components.queue_remediation_audit_card import QueueRemediationAuditCard
from app.web.components.queue_remediation_hooks_card import QueueRemediationHooksCard
from app.web.components.queue_rollup_timeline_card import QueueRollupTimelineCard
from app.web.components.quota_usage_card import QuotaUsageCard
from app.web.components.recovery_panel import RecoveryPanel
from app.web.components.run_control_panel import RunControlPanel
from app.web.components.runtime_alerts_card import RuntimeAlertsCard
from app.web.components.security_events_card import SecurityEventsCard
from app.web.components.slo_status_card import SLOStatusCard
from app.web.components.tenant_selector import TenantSelector
from app.web.components.platform_admin_forms import PlatformAdminForms
from app.web.components.platform_admin_shell import PlatformAdminShell
from app.web.components.platform_admin_workspace import PlatformAdminWorkspace
from app.web.components.platform_admin_live_renderers import PlatformAdminLiveRenderers
from app.web.payload_builder import KindedPayloadBuilder

_COMPONENT_KINDS: Final[dict[str, str]] = {
    "AutopilotButton": "autopilot_button",
    "CampaignStatusCard": "campaign_status_card",
    "ConnectorHealthCard": "connector_health_card",
    "DecisionFeed": "decision_feed",
    "GrowthSummaryCard": "growth_summary_card",
    "LeadFeed": "lead_feed",
    "MagicMomentBanner": "magic_moment_banner",
    "OnboardingChecklist": "onboarding_checklist",
    "RevenueCard": "revenue_card",
}


def _builder_type(name: str, kind: str) -> type[KindedPayloadBuilder]:
    return type(name, (KindedPayloadBuilder,), {"KIND": kind})


COMPONENT_BUILDERS: Final[dict[str, type[KindedPayloadBuilder]]] = {
    name: _builder_type(name, kind) for name, kind in _COMPONENT_KINDS.items()
}

globals().update(COMPONENT_BUILDERS)

ADMIN_COMPONENTS = {
    'ApprovalQueueCard': ApprovalQueueCard,
    'AuditLogTable': AuditLogTable,
    'AutonomyBudgetPanel': AutonomyBudgetPanel,
    'CapabilityDiagnosticsCard': CapabilityDiagnosticsCard,
    'DeadLetterPanel': DeadLetterPanel,
    'CapacityBudgetPanel': CapacityBudgetPanel,
    'EscalationHistoryPanel': EscalationHistoryPanel,
    'InferenceProviderHealthPanel': InferenceProviderHealthPanel,
    'InferenceQueuePressurePanel': InferenceQueuePressurePanel,
    'InferenceTierPanel': InferenceTierPanel,
    'InferenceVerificationPanel': InferenceVerificationPanel,
    'ManualCapacityOverridePanel': ManualCapacityOverridePanel,
    'ProviderMixPanel': ProviderMixPanel,
    'ExecutionTraceCard': ExecutionTraceCard,
    'PolicyOverrideCard': PolicyOverrideCard,
    'QueueAlertHistoryCard': QueueAlertHistoryCard,
    'QueueRollupTimelineCard': QueueRollupTimelineCard,
    'QuotaUsageCard': QuotaUsageCard,
    'QueueHealthCard': QueueHealthCard,
    'QueueRemediationHooksCard': QueueRemediationHooksCard,
    'QueueRemediationAuditCard': QueueRemediationAuditCard,
    'QueueRemediationAnalyticsCard': QueueRemediationAnalyticsCard,
    'RecoveryPanel': RecoveryPanel,
    'RunControlPanel': RunControlPanel,
    'RuntimeAlertsCard': RuntimeAlertsCard,
    'SecurityEventsCard': SecurityEventsCard,
    'SLOStatusCard': SLOStatusCard,
    'TenantSelector': TenantSelector,
    'AnalyticsDashboardCard': AnalyticsDashboardCard,
    'AnalyticsExplainabilityCard': AnalyticsExplainabilityCard,
    'AnalyticsRollupCard': AnalyticsRollupCard,
    'MonetizationDashboardCard': MonetizationDashboardCard,
    'RevenueAdvisoryCard': RevenueAdvisoryCard,
    'ClientOutcomeDashboardCard': ClientOutcomeDashboardCard,
    'PlatformAdminShell': PlatformAdminShell,
    'PlatformAdminWorkspace': PlatformAdminWorkspace,
    'PlatformAdminLiveRenderers': PlatformAdminLiveRenderers,
    'PlatformAdminForms': PlatformAdminForms,
}

globals().update(ADMIN_COMPONENTS)
install_public_api_alias(__name__)

__all__ = tuple(COMPONENT_BUILDERS) + tuple(ADMIN_COMPONENTS)
