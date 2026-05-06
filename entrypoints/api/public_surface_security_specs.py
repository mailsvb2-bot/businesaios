from __future__ import annotations

from dataclasses import dataclass

from security.access_policy import SecurityAction

CANON_API_PUBLIC_SURFACE_SECURITY_SPECS = True


@dataclass(frozen=True)
class PublicSurfaceRouteSpec:
    operation_name: str
    resource_type: str
    action: SecurityAction
    tags: tuple[str, ...]


_ROUTE_SPECS: dict[str, PublicSurfaceRouteSpec] = {

    '/client-outcome/disputes/open': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.disputes.open',
        resource_type='client_outcome_dispute',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'dispute', 'public_api'),
    ),
    '/client-outcome/disputes/reverse': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.disputes.reverse',
        resource_type='client_outcome_reversal',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'dispute', 'public_api'),
    ),
    '/client-outcome/admin-summary': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.admin_summary',
        resource_type='client_outcome_admin_summary',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'admin', 'public_api'),
    ),
    '/client-outcome/packages': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.packages',
        resource_type='client_outcome_catalog',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'public_api'),
    ),
    '/client-outcome/select': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.select',
        resource_type='client_outcome_order',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'public_api'),
    ),
    '/client-outcome/orders/{order_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.orders.get',
        resource_type='client_outcome_order',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'public_api'),
    ),
    '/client-outcome/orders/{order_id}/amend': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.orders.amend',
        resource_type='client_outcome_order',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'amendment', 'public_api'),
    ),
    '/client-outcome/commercial-state/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.commercial_state',
        resource_type='client_outcome_commercial_state',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'commercial_state', 'public_api'),
    ),
    '/client-outcome/corrected-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.corrected_economics',
        resource_type='client_outcome_corrected_economics',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'corrected_economics', 'public_api'),
    ),
    '/client-outcome/reconciliation/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.reconciliation',
        resource_type='client_outcome_reconciliation',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'reconciliation', 'public_api'),
    ),
    '/client-outcome/orders/{order_id}/{lead_id}/admin-view': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.admin_view',
        resource_type='client_outcome_admin_view',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'admin', 'public_api'),
    ),
    '/economic/truth/click-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_economics.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'public_api'),
    ),
    '/economic/truth/spend/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'public_api'),
    ),
    '/economic/export/click-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_economics.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'export', 'public_api'),
    ),
    '/economic/audit/click-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_economics.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'audit', 'public_api'),
    ),
    '/economic/export/spend/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'export', 'public_api'),
    ),
    '/economic/audit/spend/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'audit', 'public_api'),
    ),
    '/economic/handoff/click-economics/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_economics.handoff',
        resource_type='economic_handoff',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'handoff', 'public_api'),
    ),
    '/economic/manifest/spend/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend.manifest',
        resource_type='economic_manifest',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'manifest', 'public_api'),
    ),
    '/economic/truth/click-billing-invoice/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_invoice.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_invoice', 'public_api'),
    ),
    '/economic/export/click-billing-invoice/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_invoice.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_invoice', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-invoice/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_invoice.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_invoice', 'audit', 'public_api'),
    ),
    '/economic/truth/click-billing-lifecycle/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_lifecycle.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_lifecycle', 'public_api'),
    ),
    '/economic/export/click-billing-lifecycle/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_lifecycle.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_lifecycle', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-lifecycle/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_lifecycle.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_lifecycle', 'audit', 'public_api'),
    ),
    '/economic/truth/click-billing-collection/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_collection.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_collection', 'public_api'),
    ),
    '/economic/export/click-billing-collection/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_collection.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_collection', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-collection/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_collection.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_collection', 'audit', 'public_api'),
    ),

    '/economic/truth/click-billing-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_execution.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_execution', 'public_api'),
    ),
    '/economic/export/click-billing-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_execution.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_execution', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_execution.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_execution', 'audit', 'public_api'),
    ),


    '/economic/truth/click-billing-provider-dispatch/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_provider_dispatch.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_provider_dispatch', 'public_api'),
    ),
    '/economic/export/click-billing-provider-dispatch/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_provider_dispatch.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_provider_dispatch', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-provider-dispatch/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_provider_dispatch.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_provider_dispatch', 'audit', 'public_api'),
    ),
    '/economic/truth/spend-external-runtime-request/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_runtime_request.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_runtime_request', 'public_api'),
    ),
    '/economic/export/spend-external-runtime-request/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_runtime_request.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_runtime_request', 'export', 'public_api'),
    ),
    '/economic/audit/spend-external-runtime-request/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_runtime_request.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_runtime_request', 'audit', 'public_api'),
    ),
    '/economic/truth/click-billing-settlement/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_settlement.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_settlement', 'public_api'),
    ),
    '/economic/export/click-billing-settlement/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_settlement.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_settlement', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-settlement/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_settlement.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_billing_settlement', 'audit', 'public_api'),
    ),

    '/economic/truth/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_sealed_execution.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'sealed_execution', 'public_api'),
    ),
    '/economic/export/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_sealed_execution.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'sealed_execution', 'export', 'public_api'),
    ),
    '/economic/audit/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.click_billing_sealed_execution.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'click_economics', 'sealed_execution', 'audit', 'public_api'),
    ),
    '/economic/truth/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_sealed_execution.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'sealed_execution', 'public_api'),
    ),
    '/economic/export/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_sealed_execution.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'sealed_execution', 'export', 'public_api'),
    ),
    '/economic/audit/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_sealed_execution.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend', 'sealed_execution', 'audit', 'public_api'),
    ),
    '/economic/reconciliation/business/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.business_cross_domain_reconciliation',
        resource_type='economic_reconciliation',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'business_reconciliation', 'public_api'),
    ),
    '/economic/truth/spend-source-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source_ingress.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source_ingress', 'public_api'),
    ),
    '/economic/export/spend-source-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source_ingress.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source_ingress', 'export', 'public_api'),
    ),
    '/economic/audit/spend-source-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source_ingress.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source_ingress', 'audit', 'public_api'),
    ),


    '/economic/truth/spend-external-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_ingress.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_ingress', 'public_api'),
    ),
    '/economic/export/spend-external-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_ingress.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_ingress', 'export', 'public_api'),
    ),
    '/economic/audit/spend-external-ingress/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_external_ingress.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_external_ingress', 'audit', 'public_api'),
    ),
    '/economic/truth/spend-ingress-envelope/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_ingress_envelope.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_ingress_envelope', 'public_api'),
    ),
    '/economic/export/spend-ingress-envelope/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_ingress_envelope.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_ingress_envelope', 'export', 'public_api'),
    ),
    '/economic/audit/spend-ingress-envelope/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_ingress_envelope.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_ingress_envelope', 'audit', 'public_api'),
    ),
    '/economic/truth/spend-source/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source', 'public_api'),
    ),
    '/economic/export/spend-source/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source', 'export', 'public_api'),
    ),
    '/economic/audit/spend-source/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source', 'audit', 'public_api'),
    ),
    '/economic/manifest/spend-source/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.spend_source.manifest',
        resource_type='economic_manifest',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'spend_source', 'manifest', 'public_api'),
    ),
    '/economic/truth/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.client_outcome.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'client_outcome', 'public_api'),
    ),
    '/economic/export/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.client_outcome.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'client_outcome', 'export', 'public_api'),
    ),
    '/economic/truth/business/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.business.truth',
        resource_type='economic_truth',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'business', 'public_api'),
    ),
    '/economic/export/business/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.business.export',
        resource_type='economic_export',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'business', 'export', 'public_api'),
    ),
    '/economic/audit/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.client_outcome.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'client_outcome', 'audit', 'public_api'),
    ),
    '/economic/audit/business/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.business.audit',
        resource_type='economic_audit',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'business', 'audit', 'public_api'),
    ),
    '/economic/anomalies/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.client_outcome.anomalies',
        resource_type='economic_anomalies',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'client_outcome', 'anomalies', 'public_api'),
    ),
    '/economic/anomalies/business/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.business.anomalies',
        resource_type='economic_anomalies',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'business', 'anomalies', 'public_api'),
    ),
    '/client-outcome/lifecycle/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.lifecycle',
        resource_type='client_outcome_lifecycle',
        action=SecurityAction.READ,
        tags=('internal', 'client_outcome', 'lifecycle', 'public_api'),
    ),
    '/client-outcome/execute': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.execute',
        resource_type='client_outcome_execution',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'public_api'),
    ),
    '/client-outcome/full-cycle': PublicSurfaceRouteSpec(
        operation_name='api.public.client_outcome.full_cycle',
        resource_type='client_outcome_execution',
        action=SecurityAction.WRITE,
        tags=('internal', 'client_outcome', 'e2e', 'public_api'),
    ),
    '/actions/execute': PublicSurfaceRouteSpec(
        operation_name='api.public.execute_action',
        resource_type='execute_action',
        action=SecurityAction.WRITE,
        tags=('internal', 'execute_action', 'public_api'),
    ),
    '/goals/execute': PublicSurfaceRouteSpec(
        operation_name='api.public.execute_goal',
        resource_type='goal_execution',
        action=SecurityAction.WRITE,
        tags=('internal', 'goal_execution', 'public_api'),
    ),
    '/baselines/promote': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.promote',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/baselines/select': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.select',
        resource_type='governance_baseline',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/drift/audit': PublicSurfaceRouteSpec(
        operation_name='api.public.drift.audit',
        resource_type='drift_audit',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'drift', 'public_api'),
    ),
    '/baselines/rollback': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.rollback',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'rollback', 'public_api'),
    ),
    '/business-memory/get': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.get',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/summary': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.summary',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/recent-runs': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.recent_runs',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/failures': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.failures',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/wins': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.wins',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/governance/rollback-recommendation': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.rollback_recommendation',
        resource_type='governance_analytics',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'analytics', 'public_api'),
    ),
    '/governance/joined-history': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.joined_history',
        resource_type='governance_history',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'history', 'public_api'),
    ),
    '/governance/verify-promotion-evidence': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.verify_promotion_evidence',
        resource_type='governance_evidence',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'evidence', 'public_api'),
    ),
    '/governance/promote-scenario': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.promote_scenario',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/governance/rollback-timeline': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.rollback_timeline',
        resource_type='governance_timeline',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'timeline', 'public_api'),
    ),
    '/governance/drift-trend': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.drift_trend',
        resource_type='governance_analytics',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'analytics', 'public_api'),
    ),
    '/governance/business-memory-summary': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.business_memory_summary',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'governance', 'public_api'),
    ),
    '/analytics/business/{tenant_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.analytics.business_scorecard',
        resource_type='analytics_scorecard',
        action=SecurityAction.READ,
        tags=('internal', 'analytics', 'business', 'public_api'),
    ),
    '/analytics/dashboard/{tenant_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.analytics.dashboard_bundle',
        resource_type='analytics_dashboard',
        action=SecurityAction.READ,
        tags=('internal', 'analytics', 'dashboard', 'public_api'),
    ),
}



__all__ = ['CANON_API_PUBLIC_SURFACE_SECURITY_SPECS', 'PublicSurfaceRouteSpec', '_ROUTE_SPECS']
