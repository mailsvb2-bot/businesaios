from __future__ import annotations

"""Extracted owner logic for ClientOutcomeRouteHandlers."""

from datetime import datetime, timezone

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
from billing.client_outcome_revenue_control_service import ClientOutcomeRevenueControlService
from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from billing.client_outcome_reversal_ledger_bridge import ClientOutcomeReversalLedgerBridge
from billing.client_outcome_reversal_posting_service import ClientOutcomeReversalPostingService
from billing.client_outcome_usage_ledger import ClientOutcomeUsageAppender, ClientOutcomeUsageLedger
from billing.ledger_store import InMemoryLedgerStore
from economics.client_outcome_economic_calculator import ClientOutcomeEconomicCalculator
from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest, ClientOutcomeAdminSummaryResponse
from entrypoints.api.client_outcome_admin_view_models import ClientOutcomeAdminViewResponse
from entrypoints.api.client_outcome_commercial_state_models import ClientOutcomeCommercialStateResponse
from entrypoints.api.client_outcome_corrected_economics_models import ClientOutcomeCorrectedEconomicsResponse
from entrypoints.api.client_outcome_reconciliation_models import ClientOutcomeReconciliationResponse
from entrypoints.api.client_outcome_cycle_models import (
    ClientOutcomeRevenueResponse,
    ClientOutcomeVerificationResponse,
    ExecuteClientOutcomeCycleRequest,
    ExecuteClientOutcomeCycleResponse,
)
from entrypoints.api.client_outcome_dispute_models import (
    ClientOutcomeBillableRecordInput,
    ClientOutcomeDisputeResponse,
    ClientOutcomeReversalResponse,
    OpenClientOutcomeDisputeRequest,
    ReverseClientOutcomeDisputeRequest,
)
from entrypoints.api.client_outcome_lifecycle_models import ClientOutcomeLifecycleResponse
from entrypoints.api.client_outcome_models import (
    AmendClientOutcomeOrderRequest,
    ClientOutcomeExecuteResponse,
    ClientOutcomeOrderAmendResponse,
    ClientOutcomeOrderLookupResponse,
    ClientOutcomeOrderResponse,
    ClientOutcomePackageResponse,
    SelectClientOutcomePackageRequest,
)
from lead_outcomes import OutcomeVerifier
from lead_outcomes.client_attribution_policy import ClientAttributionPolicy
from lead_outcomes.client_eligibility_policy import ClientEligibilityPolicy
from lead_outcomes.client_fraud_policy import ClientFraudPolicy
from lead_outcomes.client_outcome_commercial_state_store import (
    ClientOutcomeCommercialStateService,
    ClientOutcomeCommercialStateStore,
)
from lead_outcomes.client_outcome_contract import (
    BillableClientRecord,
    ClientOutcomeOrder,
    ClientOutcomePackage,
    ClientProofEvent,
    OutcomeLead,
)
from lead_outcomes.client_outcome_corrected_economics_store import (
    ClientOutcomeCorrectedEconomicsService,
    ClientOutcomeCorrectedEconomicsStore,
)
from lead_outcomes.client_outcome_reconciliation_service import ClientOutcomeReconciliationService
from lead_outcomes.client_outcome_cycle_idempotency_store import (
    ClientOutcomeCycleIdempotencyService,
    ClientOutcomeCycleIdempotencyStore,
)
from lead_outcomes.client_outcome_lifecycle_store import (
    ClientOutcomeLifecyclePersistenceService,
    ClientOutcomeLifecycleStore,
)
from lead_outcomes.client_outcome_order_factory import ClientOutcomeOrderFactory
from lead_outcomes.client_outcome_order_store import ClientOutcomeOrderPersistenceService, ClientOutcomeOrderStore
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog
from lead_outcomes.client_outcome_registry import ClientOutcomeRegistry
from lead_outcomes.client_outcome_selection_service import ClientOutcomeSelectionInput, ClientOutcomeSelectionService
from lead_outcomes.client_outcome_service import ClientOutcomeService
from lead_outcomes.client_verification_service import ClientVerificationService
from registry.base_registry import BaseRegistry
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry
from runtime.economic_core.client_outcome_bridge import build_client_outcome_truth_snapshot
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export


from entrypoints.api.client_outcome_routes.module_helpers import (
    _billable_record_from_input,
    _billable_record_payload,
    _merge_billable_record_metadata,
    _order_from_input,
    _order_from_response,
    _present_order,
    _revenue_payload,
)

def list_packages(handlers) -> tuple[ClientOutcomePackageResponse, ...]:
    return tuple(
        ClientOutcomePackageResponse(
            package_id=package.package_id,
            label=package.label,
            requested_clients=package.requested_clients,
            price_per_verified_client=package.price_per_verified_client,
            currency=package.currency,
            attribution_window_days=package.attribution_window_days,
            trust_tier=package.trust_tier,
        )
        for package in handlers.package_catalog.list_packages()
    )

def select_package(handlers, *, now: datetime, request: SelectClientOutcomePackageRequest) -> ClientOutcomeOrderResponse:
    selection = handlers.selection_service.select(
        now=now,
        request=ClientOutcomeSelectionInput(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    return _present_order(selection.order)

def get_order(handlers, *, order_id: str) -> ClientOutcomeOrderLookupResponse:
    order = handlers.selection_service.get_order(order_id)
    if order is None:
        return ClientOutcomeOrderLookupResponse(found=False, order=None)
    return ClientOutcomeOrderLookupResponse(found=True, order=_present_order(order))

def amend_order(handlers, *, now: datetime, order_id: str, request: AmendClientOutcomeOrderRequest) -> ClientOutcomeOrderAmendResponse:
    current_order = handlers.selection_service.get_order(order_id)
    if current_order is None:
        raise KeyError(order_id)
    selection = handlers.selection_service.amend(
        now=now,
        order_id=order_id,
        request=ClientOutcomeSelectionInput(
            tenant_id=current_order.tenant_id,
            business_id=current_order.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    if selection is None:
        raise KeyError(order_id)
    order = selection.order
    amendments = tuple(dict(item) for item in (order.metadata.get('amendments') or ()))
    return ClientOutcomeOrderAmendResponse(
        order=_present_order(order),
        amendment_count=int(order.metadata.get('amendment_count') or 0),
        amendments=amendments,
    )

def execute_package(handlers, *, now: datetime, request: SelectClientOutcomePackageRequest) -> ClientOutcomeExecuteResponse:
    selection = handlers.selection_service.select(
        now=now,
        request=ClientOutcomeSelectionInput(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    order = selection.order
    enriched_meta = handlers.request_enricher.enrich_metadata(existing_metadata=request.metadata, order=order)
    execution_payload = {
        'mode': 'prepared_contract',
        'goal': f'Acquire {order.package.requested_clients} verified new clients for business {order.business_id} within {order.package.attribution_window_days} days',
        'business_id': order.business_id,
        'tenant_id': order.tenant_id,
        'completed': False,
        'stop_reason': 'prepared_for_headless_execution',
        'steps': [],
        'final_feedback': dict(enriched_meta),
        'capability_view': {},
    }
    return ClientOutcomeExecuteResponse(order=_present_order(order), execution=execution_payload)
