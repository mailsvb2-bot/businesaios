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

def open_dispute(handlers, *, now: datetime, request: OpenClientOutcomeDisputeRequest) -> ClientOutcomeDisputeResponse:
    record = _billable_record_from_input(request.record)
    case = handlers.dispute_service.open_dispute(
        now=now,
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        order_id=request.order_id,
        lead_id=request.lead_id,
        billable_record_id=record.record_id,
        opened_by=request.opened_by,
        reason_code=request.reason_code,
        notes=request.notes,
        record=record,
        metadata=request.metadata,
    )
    meta = dict(case.metadata)
    return ClientOutcomeDisputeResponse(
        dispute_id=case.dispute_id,
        status=case.status,
        reason_code=case.reason_code,
        resolution_code=case.resolution_code,
        classification_case_type=str(meta.get('classification_case_type') or ''),
        classification_severity=str(meta.get('classification_severity') or ''),
        evidence_fingerprint=str(meta.get('evidence_fingerprint') or ''),
    )

def reverse_dispute(handlers, *, now: datetime, request: ReverseClientOutcomeDisputeRequest) -> ClientOutcomeReversalResponse:
    case = handlers.dispute_service.get_case(request.dispute_id)
    if case is None:
        raise KeyError(request.dispute_id)
    original_record = _billable_record_from_input(request.record)
    result = handlers.dispute_service.accept_and_reverse(
        now=now,
        case=case,
        original_record=original_record,
        reversal_amount=request.reversal_amount,
    )
    if result.reversal_payload is None:
        return ClientOutcomeReversalResponse(
            dispute_id=case.dispute_id,
            status=result.dispute.status,
            negative_record_id=None,
            reversal_id=None,
            ledger_posting_id=None,
            amount=None,
            currency=None,
            partial_reversal=False,
            refund_preview=None,
        )
    reversal = ClientOutcomeReversalRecord(
        reversal_id=str(result.reversal_payload['reversal_id']),
        tenant_id=case.tenant_id,
        business_id=case.business_id,
        order_id=case.order_id,
        lead_id=case.lead_id,
        original_billable_record_id=original_record.record_id,
        negative_record_id=str(result.reversal_payload['negative_record_id']),
        created_at=now,
        reason_code=case.reason_code,
        amount=float(result.reversal_payload['amount']),
        currency=str(result.reversal_payload['currency']),
        metadata={'source': 'reverse_dispute'},
    )
    posting_result = handlers.reversal_posting_service.append_reversal(reversal=reversal, booked_at=now)
    refund_preview = handlers.refund_projection.build_preview(original_record=original_record, reversal=reversal, user_id=case.opened_by)
    return ClientOutcomeReversalResponse(
        dispute_id=case.dispute_id,
        status=result.dispute.status,
        negative_record_id=None if result.negative_record is None else result.negative_record.record_id,
        reversal_id=reversal.reversal_id,
        ledger_posting_id=posting_result.posting.posting_id,
        amount=reversal.amount,
        currency=reversal.currency,
        partial_reversal=bool(result.reversal_payload.get('partial_reversal')),
        refund_preview=refund_preview,
    )
