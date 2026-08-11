from __future__ import annotations

from dataclasses import dataclass

from security.access_policy import SecurityAction


@dataclass(frozen=True)
class PublicSurfaceRouteSpec:
    operation_name: str
    resource_type: str
    action: SecurityAction
    tags: tuple[str, ...]


_ROUTE_SPECS: dict[str, PublicSurfaceRouteSpec] = {
    '/actions/execute': PublicSurfaceRouteSpec('api.public.execute_action', 'execute_action', SecurityAction.WRITE, ('internal', 'execute_action', 'public_api')),
    '/goals/execute': PublicSurfaceRouteSpec('api.public.execute_goal', 'goal_execution', SecurityAction.WRITE, ('internal', 'goal_execution', 'public_api')),
    '/baselines/promote': PublicSurfaceRouteSpec('api.public.baselines.promote', 'governance_baseline', SecurityAction.ADMIN, ('internal', 'governance', 'baseline', 'public_api')),
    '/baselines/select': PublicSurfaceRouteSpec('api.public.baselines.select', 'governance_baseline', SecurityAction.READ, ('internal', 'governance', 'baseline', 'public_api')),
    '/drift/audit': PublicSurfaceRouteSpec('api.public.drift.audit', 'drift_audit', SecurityAction.READ, ('internal', 'governance', 'drift', 'public_api')),
    '/baselines/rollback': PublicSurfaceRouteSpec('api.public.baselines.rollback', 'governance_baseline', SecurityAction.ADMIN, ('internal', 'governance', 'rollback', 'public_api')),
    '/business-memory/get': PublicSurfaceRouteSpec('api.public.business_memory.get', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'public_api')),
    '/business-memory/summary': PublicSurfaceRouteSpec('api.public.business_memory.summary', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'public_api')),
    '/business-memory/recent-runs': PublicSurfaceRouteSpec('api.public.business_memory.recent_runs', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'public_api')),
    '/business-memory/failures': PublicSurfaceRouteSpec('api.public.business_memory.failures', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'public_api')),
    '/business-memory/wins': PublicSurfaceRouteSpec('api.public.business_memory.wins', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'public_api')),
    '/governance/rollback-recommendation': PublicSurfaceRouteSpec('api.public.governance.rollback_recommendation', 'governance_analytics', SecurityAction.READ, ('internal', 'governance', 'analytics', 'public_api')),
    '/governance/joined-history': PublicSurfaceRouteSpec('api.public.governance.joined_history', 'governance_history', SecurityAction.READ, ('internal', 'governance', 'history', 'public_api')),
    '/governance/verify-promotion-evidence': PublicSurfaceRouteSpec('api.public.governance.verify_promotion_evidence', 'governance_evidence', SecurityAction.READ, ('internal', 'governance', 'evidence', 'public_api')),
    '/governance/promote-scenario': PublicSurfaceRouteSpec('api.public.governance.promote_scenario', 'governance_baseline', SecurityAction.ADMIN, ('internal', 'governance', 'baseline', 'public_api')),
    '/governance/rollback-timeline': PublicSurfaceRouteSpec('api.public.governance.rollback_timeline', 'governance_timeline', SecurityAction.READ, ('internal', 'governance', 'timeline', 'public_api')),
    '/governance/drift-trend': PublicSurfaceRouteSpec('api.public.governance.drift_trend', 'governance_analytics', SecurityAction.READ, ('internal', 'governance', 'analytics', 'public_api')),
    '/governance/business-memory-summary': PublicSurfaceRouteSpec('api.public.governance.business_memory_summary', 'business_memory', SecurityAction.READ, ('internal', 'business_memory', 'governance', 'public_api')),
    '/analytics/business/{tenant_id}': PublicSurfaceRouteSpec('api.public.analytics.business_scorecard', 'analytics_scorecard', SecurityAction.READ, ('internal', 'analytics', 'business', 'public_api')),
    '/analytics/dashboard/{tenant_id}': PublicSurfaceRouteSpec('api.public.analytics.dashboard_bundle', 'analytics_dashboard', SecurityAction.READ, ('internal', 'analytics', 'dashboard', 'public_api')),
    '/economic/truth/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.truth.click_billing_sealed_execution', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'truth', 'click_billing', 'public_api')),
    '/economic/export/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.export.click_billing_sealed_execution', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'export', 'click_billing', 'public_api')),
    '/economic/audit/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.audit.click_billing_sealed_execution', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'audit', 'click_billing', 'public_api')),
    '/economic/truth/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.truth.spend_external_sealed_execution_client_outcome', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'truth', 'spend_external', 'client_outcome', 'public_api')),
    '/economic/export/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.export.spend_external_sealed_execution_client_outcome', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'export', 'spend_external', 'client_outcome', 'public_api')),
    '/economic/audit/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.audit.spend_external_sealed_execution_client_outcome', 'economic_sealed_execution', SecurityAction.READ, ('internal', 'economic', 'sealed_execution', 'audit', 'spend_external', 'client_outcome', 'public_api')),
    '/client-outcome/packages': PublicSurfaceRouteSpec('api.public.client_outcome.packages', 'client_outcome_catalog', SecurityAction.READ, ('internal', 'client_outcome', 'catalog', 'public_api')),
    '/client-outcome/select': PublicSurfaceRouteSpec('api.public.client_outcome.select', 'client_outcome_order', SecurityAction.WRITE, ('internal', 'client_outcome', 'order', 'public_api')),
    '/client-outcome/orders/{order_id}': PublicSurfaceRouteSpec('api.public.client_outcome.order', 'client_outcome_order', SecurityAction.READ, ('internal', 'client_outcome', 'order', 'public_api')),
    '/client-outcome/orders/{order_id}/amend': PublicSurfaceRouteSpec('api.public.client_outcome.order_amend', 'client_outcome_order', SecurityAction.WRITE, ('internal', 'client_outcome', 'order', 'amendment', 'public_api')),
    '/client-outcome/execute': PublicSurfaceRouteSpec('api.public.client_outcome.execute', 'client_outcome_execution', SecurityAction.WRITE, ('internal', 'client_outcome', 'execution', 'public_api')),
    '/client-outcome/disputes/open': PublicSurfaceRouteSpec('api.public.client_outcome.disputes.open', 'client_outcome_dispute', SecurityAction.WRITE, ('internal', 'client_outcome', 'dispute', 'public_api')),
    '/client-outcome/disputes/reverse': PublicSurfaceRouteSpec('api.public.client_outcome.disputes.reverse', 'client_outcome_dispute', SecurityAction.ADMIN, ('internal', 'client_outcome', 'dispute', 'reversal', 'public_api')),
    '/client-outcome/full-cycle': PublicSurfaceRouteSpec('api.public.client_outcome.full_cycle', 'client_outcome_cycle', SecurityAction.WRITE, ('internal', 'client_outcome', 'cycle', 'public_api')),
    '/client-outcome/lifecycle/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.client_outcome.lifecycle', 'client_outcome_lifecycle', SecurityAction.READ, ('internal', 'client_outcome', 'lifecycle', 'public_api')),
    '/client-outcome/commercial-state/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.client_outcome.commercial_state', 'client_outcome_commercial_state', SecurityAction.READ, ('internal', 'client_outcome', 'commercial_state', 'public_api')),
    '/client-outcome/corrected-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.client_outcome.corrected_economics', 'client_outcome_economics', SecurityAction.READ, ('internal', 'client_outcome', 'economics', 'public_api')),
    '/client-outcome/reconciliation/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.client_outcome.reconciliation', 'client_outcome_reconciliation', SecurityAction.READ, ('internal', 'client_outcome', 'reconciliation', 'public_api')),
    '/client-outcome/orders/{order_id}/{lead_id}/admin-view': PublicSurfaceRouteSpec('api.public.client_outcome.admin_view', 'client_outcome_admin', SecurityAction.ADMIN, ('internal', 'client_outcome', 'admin', 'public_api')),
    '/client-outcome/admin-summary': PublicSurfaceRouteSpec('api.public.client_outcome.admin_summary', 'client_outcome_admin', SecurityAction.ADMIN, ('internal', 'client_outcome', 'admin', 'public_api')),
    '/economic/client-outcome-truth/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.client_outcome_truth', 'economic_client_outcome_truth', SecurityAction.READ, ('internal', 'economic', 'client_outcome', 'truth', 'public_api')),
    '/economic/business-truth/{order_id}/{lead_id}': PublicSurfaceRouteSpec('api.public.economic.business_truth', 'economic_business_truth', SecurityAction.READ, ('internal', 'economic', 'business', 'truth', 'public_api')),
    '/public-site/integrations': PublicSurfaceRouteSpec('api.public.public_site.integrations', 'public_site_integration_catalog', SecurityAction.READ, ('public', 'public_site', 'integrations', 'public_api')),
    '/public-site/acquisition/feasibility': PublicSurfaceRouteSpec('api.public.public_site.acquisition_feasibility', 'acquisition_scenario', SecurityAction.READ, ('public', 'public_site', 'acquisition', 'public_api')),
    '/public-site/cta/start': PublicSurfaceRouteSpec('api.public.public_site.cta_start', 'public_site_cta_intake', SecurityAction.WRITE, ('public', 'public_site', 'cta', 'public_api')),
    '/public-site/cta/{intake_id}': PublicSurfaceRouteSpec('api.public.public_site.cta_status', 'public_site_cta_intake', SecurityAction.READ, ('public', 'public_site', 'cta', 'public_api')),
}


__all__ = ['PublicSurfaceRouteSpec', '_ROUTE_SPECS']
