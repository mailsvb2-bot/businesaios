from __future__ import annotations

from dataclasses import dataclass

from admin.client_outcome_control_plane_service import ClientOutcomeControlPlaneService
from application.headless.client_outcome_request_enricher import ClientOutcomeRequestEnricher
from billing.client_outcome_billable_cap_policy import ClientOutcomeBillableCapPolicy
from billing.client_outcome_dispute_service import ClientOutcomeDisputeService
from billing.client_outcome_dispute_store import ClientOutcomeDisputeStore, ClientOutcomeReversalStore
from billing.client_outcome_invoice_aggregator import ClientOutcomeInvoiceAggregator
from billing.client_outcome_negative_usage_builder import ClientOutcomeNegativeUsageBuilder
from billing.client_outcome_package_progress import ClientOutcomePackageProgressCalculator
from billing.client_outcome_refund_projection import ClientOutcomeRefundProjection
from billing.client_outcome_refund_request_bridge import ClientOutcomeRefundRequestBridge
from billing.client_outcome_refund_window_policy import ClientOutcomeRefundWindowPolicy
from billing.client_outcome_reversal_ledger_bridge import ClientOutcomeReversalLedgerBridge
from billing.client_outcome_reversal_posting_service import ClientOutcomeReversalPostingService
from billing.client_outcome_revenue_control_service import ClientOutcomeRevenueControlService
from billing.client_outcome_usage_ledger import ClientOutcomeUsageAppender, ClientOutcomeUsageLedger
from billing.ledger_store import InMemoryLedgerStore
from economics.client_outcome_economic_calculator import ClientOutcomeEconomicCalculator
from entrypoints.api.client_outcome_routes import service as client_service
from lead_outcomes import OutcomeVerifier
from lead_outcomes.client_attribution_policy import ClientAttributionPolicy
from lead_outcomes.client_eligibility_policy import ClientEligibilityPolicy
from lead_outcomes.client_fraud_policy import ClientFraudPolicy
from lead_outcomes.client_outcome_commercial_state_store import ClientOutcomeCommercialStateService, ClientOutcomeCommercialStateStore
from lead_outcomes.client_outcome_corrected_economics_store import ClientOutcomeCorrectedEconomicsService, ClientOutcomeCorrectedEconomicsStore
from lead_outcomes.client_outcome_cycle_idempotency_store import ClientOutcomeCycleIdempotencyService, ClientOutcomeCycleIdempotencyStore
from lead_outcomes.client_outcome_lifecycle_store import ClientOutcomeLifecyclePersistenceService, ClientOutcomeLifecycleStore
from lead_outcomes.client_outcome_order_factory import ClientOutcomeOrderFactory
from lead_outcomes.client_outcome_order_store import ClientOutcomeOrderPersistenceService, ClientOutcomeOrderStore
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog
from lead_outcomes.client_outcome_reconciliation_service import ClientOutcomeReconciliationService
from lead_outcomes.client_outcome_registry import ClientOutcomeRegistry
from lead_outcomes.client_outcome_selection_service import ClientOutcomeSelectionService
from lead_outcomes.client_outcome_service import ClientOutcomeService
from lead_outcomes.client_verification_service import ClientVerificationService
from observability.tenant_metrics_registry import TenantMetricsRegistry
from registry.base_registry import BaseRegistry

CANON_CLIENT_OUTCOME_ROUTE_HANDLERS = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeRouteHandlers:
    package_catalog: ClientOutcomePackageCatalog
    selection_service: ClientOutcomeSelectionService
    request_enricher: ClientOutcomeRequestEnricher
    dispute_service: ClientOutcomeDisputeService
    control_plane_service: ClientOutcomeControlPlaneService
    reversal_posting_service: ClientOutcomeReversalPostingService
    refund_projection: ClientOutcomeRefundProjection
    refund_request_bridge: ClientOutcomeRefundRequestBridge
    client_outcome_service: ClientOutcomeService
    revenue_control_service: ClientOutcomeRevenueControlService
    lifecycle_service: ClientOutcomeLifecyclePersistenceService
    commercial_state_service: ClientOutcomeCommercialStateService
    corrected_economics_service: ClientOutcomeCorrectedEconomicsService
    reconciliation_service: ClientOutcomeReconciliationService
    cycle_idempotency_service: ClientOutcomeCycleIdempotencyService
    tenant_metrics_registry: TenantMetricsRegistry


def build_client_outcome_route_handlers(*, headless_handlers: object | None = None) -> ClientOutcomeRouteHandlers:
    package_catalog = ClientOutcomePackageCatalog.default_catalog()
    order_factory = ClientOutcomeOrderFactory(package_catalog=package_catalog)
    order_store = ClientOutcomeOrderStore()
    dispute_store = ClientOutcomeDisputeStore()
    reversal_store = ClientOutcomeReversalStore(registry=BaseRegistry(kind='client_outcome_reversal'))
    dispute_service = ClientOutcomeDisputeService(
        dispute_store=dispute_store,
        reversal_store=reversal_store,
        refund_window_policy=ClientOutcomeRefundWindowPolicy(refund_window_days=14),
        negative_usage_builder=ClientOutcomeNegativeUsageBuilder(),
    )
    control_plane_service = ClientOutcomeControlPlaneService(dispute_service=dispute_service)
    reversal_posting_service = ClientOutcomeReversalPostingService(
        ledger_store=InMemoryLedgerStore(),
        ledger_bridge=ClientOutcomeReversalLedgerBridge(),
    )
    client_outcome_service = ClientOutcomeService(
        registry=ClientOutcomeRegistry(),
        verification_service=ClientVerificationService(
            attribution_policy=ClientAttributionPolicy(),
            fraud_policy=ClientFraudPolicy(),
            eligibility_policy=ClientEligibilityPolicy(),
            outcome_verifier=OutcomeVerifier(),
        ),
    )
    lifecycle_store = ClientOutcomeLifecycleStore()
    commercial_state_store = ClientOutcomeCommercialStateStore()
    corrected_economics_store = ClientOutcomeCorrectedEconomicsStore()
    cycle_idempotency_store = ClientOutcomeCycleIdempotencyStore()
    tenant_metrics_registry = TenantMetricsRegistry()
    lifecycle_service = ClientOutcomeLifecyclePersistenceService(store=lifecycle_store)
    commercial_state_service = ClientOutcomeCommercialStateService(store=commercial_state_store)
    corrected_economics_service = ClientOutcomeCorrectedEconomicsService(store=corrected_economics_store)
    selection_service = ClientOutcomeSelectionService(
        package_catalog=package_catalog,
        order_factory=order_factory,
        persistence_service=ClientOutcomeOrderPersistenceService(store=order_store),
        commercial_state_service=commercial_state_service,
    )
    reconciliation_service = ClientOutcomeReconciliationService(
        commercial_state_service=commercial_state_service,
        corrected_economics_service=corrected_economics_service,
        lifecycle_service=lifecycle_service,
    )
    usage_ledger = ClientOutcomeUsageLedger()
    revenue_control_service = ClientOutcomeRevenueControlService(
        usage_ledger=usage_ledger,
        usage_appender=ClientOutcomeUsageAppender(ledger=usage_ledger),
        progress_calculator=ClientOutcomePackageProgressCalculator(),
        billable_cap_policy=ClientOutcomeBillableCapPolicy(),
        invoice_aggregator=ClientOutcomeInvoiceAggregator(),
        economic_calculator=ClientOutcomeEconomicCalculator(),
    )
    return ClientOutcomeRouteHandlers(
        package_catalog=package_catalog,
        selection_service=selection_service,
        request_enricher=ClientOutcomeRequestEnricher(),
        dispute_service=dispute_service,
        control_plane_service=control_plane_service,
        reversal_posting_service=reversal_posting_service,
        refund_projection=ClientOutcomeRefundProjection(),
        refund_request_bridge=ClientOutcomeRefundRequestBridge(),
        client_outcome_service=client_outcome_service,
        revenue_control_service=revenue_control_service,
        lifecycle_service=lifecycle_service,
        commercial_state_service=commercial_state_service,
        corrected_economics_service=corrected_economics_service,
        reconciliation_service=reconciliation_service,
        cycle_idempotency_service=ClientOutcomeCycleIdempotencyService(store=cycle_idempotency_store),
        tenant_metrics_registry=tenant_metrics_registry,
    )

for _name in [
    'list_packages','select_package','get_order','amend_order','execute_package','open_dispute','reverse_dispute',
    'get_lifecycle','get_commercial_state','get_corrected_economics','_resolve_tenant_id','_emit_reconciliation_metrics',
    '_build_operational_metrics_widget','_build_economic_truth_widget','_build_recovery_bridge_widget',
    'get_reconciliation','get_admin_view','build_admin_summary','execute_full_cycle'
]:
    if hasattr(client_service, _name):
        setattr(ClientOutcomeRouteHandlers, _name, getattr(client_service, _name))
