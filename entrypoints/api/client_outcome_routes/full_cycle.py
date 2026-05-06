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

def execute_full_cycle(handlers, *, now: datetime, request: ExecuteClientOutcomeCycleRequest) -> ExecuteClientOutcomeCycleResponse:
    if request.idempotency_key:
        existing = handlers.cycle_idempotency_service.get_response(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            lead_id=request.lead.lead_id,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None:
            return ExecuteClientOutcomeCycleResponse(**dict(existing['response']))

    selection_request = SelectClientOutcomePackageRequest(
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        package_id=request.package_id,
        requested_clients=request.requested_clients,
        metadata=request.metadata,
        execute_now=True,
    )
    execution_response = handlers.execute_package(now=now, request=selection_request)
    order = _order_from_response(execution_response.order)
    handlers.lifecycle_service.record_stage(
        order_id=order.order_id,
        lead_id=request.lead.lead_id,
        stage_name='selected_and_executed',
        now=now,
        payload={'order': execution_response.order.model_dump(), 'execution': execution_response.execution},
    )
    handlers.commercial_state_service.record_selected_execution(
        order_id=order.order_id,
        lead_id=request.lead.lead_id,
        now=now,
        order_payload=execution_response.order.model_dump(),
        execution_payload=execution_response.execution,
    )

    lead = OutcomeLead(
        lead_id=request.lead.lead_id,
        order_id=order.order_id,
        business_id=order.business_id,
        tenant_id=order.tenant_id,
        captured_at=datetime.fromisoformat(request.lead.captured_at),
        tracking_token=request.lead.tracking_token,
        source_channel=request.lead.source_channel,
        session_id=request.lead.session_id,
        click_id=request.lead.click_id,
        phone_hash=request.lead.phone_hash,
        email_hash=request.lead.email_hash,
        external_customer_id=request.lead.external_customer_id,
        metadata=request.lead.metadata,
    )
    proofs = tuple(
        ClientProofEvent(
            proof_id=item.proof_id,
            lead_id=lead.lead_id,
            business_id=order.business_id,
            tenant_id=order.tenant_id,
            occurred_at=datetime.fromisoformat(item.occurred_at),
            proof_type=item.proof_type,
            status=item.status,
            source=item.source,
            external_ref=item.external_ref,
            amount=item.amount,
            currency=item.currency,
            metadata=item.metadata,
        )
        for item in request.proofs
    )
    handlers.lifecycle_service.record_stage(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        stage_name='lead_captured',
        now=now,
        payload={
            'source_channel': lead.source_channel,
            'tracking_token': lead.tracking_token,
            'session_id': lead.session_id,
            'click_id': lead.click_id,
            'phone_hash_present': bool(lead.phone_hash),
            'email_hash_present': bool(lead.email_hash),
        },
    )
    verification_result = handlers.client_outcome_service.evaluate_lead(
        now=now,
        order=order,
        lead=lead,
        proofs=proofs,
        related_leads=(lead,),
        historical_leads=(),
    )
    billable_record = None if verification_result.billable_record is None else _merge_billable_record_metadata(
        verification_result.billable_record,
        dict(request.metadata),
        dict(request.lead.metadata),
    )
    verification_payload = {
        'verified': verification_result.verdict.verified,
        'billable': verification_result.verdict.billable,
        'reason_code': verification_result.verdict.reason_code,
        'confidence': verification_result.verdict.confidence,
        'proof_refs': list(verification_result.verdict.proof_refs),
        'attributed': verification_result.verdict.attribution.attributed,
        'fraud_score': verification_result.verdict.fraud.fraud_score,
        'eligibility_category': verification_result.verdict.eligibility.category,
    }
    handlers.lifecycle_service.record_stage(order_id=order.order_id, lead_id=lead.lead_id, stage_name='verified', now=now, payload=verification_payload)
    handlers.commercial_state_service.record_verification(order_id=order.order_id, lead_id=lead.lead_id, now=now, payload=verification_payload)

    revenue_before = handlers.revenue_control_service.process(
        now=now,
        order=order,
        verified_clients=1 if verification_result.verdict.verified else 0,
        existing_billable_records=(),
        new_records=() if billable_record is None else (billable_record,),
        acquisition_cost=request.acquisition_cost,
    )
    handlers.lifecycle_service.record_stage(order_id=order.order_id, lead_id=lead.lead_id, stage_name='billed', now=now, payload=_revenue_payload(revenue_before).model_dump())
    handlers.commercial_state_service.record_billing(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        now=now,
        billable_record=None if billable_record is None else _billable_record_payload(billable_record),
        revenue_payload=_revenue_payload(revenue_before).model_dump(),
    )

    dispute_payload = None
    reversal_payload = None
    corrected_revenue = revenue_before
    if request.dispute_reason_code and billable_record is not None:
        dispute_case = handlers.dispute_service.open_dispute(
            now=now,
            tenant_id=order.tenant_id,
            business_id=order.business_id,
            order_id=order.order_id,
            lead_id=lead.lead_id,
            billable_record_id=billable_record.record_id,
            opened_by=request.dispute_opened_by or 'system',
            reason_code=request.dispute_reason_code,
            record=billable_record,
            metadata={'source': 'execute_full_cycle'},
        )
        dispute_payload = {
            'dispute_id': dispute_case.dispute_id,
            'status': dispute_case.status,
            'reason_code': dispute_case.reason_code,
            'resolution_code': dispute_case.resolution_code,
            **dict(dispute_case.metadata),
        }
        handlers.lifecycle_service.record_stage(order_id=order.order_id, lead_id=lead.lead_id, stage_name='dispute_opened', now=now, payload=dispute_payload)
        handlers.commercial_state_service.record_dispute(order_id=order.order_id, lead_id=lead.lead_id, now=now, dispute_payload=dispute_payload)
        reversal_result = handlers.dispute_service.accept_and_reverse(
            now=now,
            case=dispute_case,
            original_record=billable_record,
            reversal_amount=request.dispute_reversal_amount,
        )
        if reversal_result.reversal_payload is not None:
            reversal = ClientOutcomeReversalRecord(
                reversal_id=str(reversal_result.reversal_payload['reversal_id']),
                tenant_id=order.tenant_id,
                business_id=order.business_id,
                order_id=order.order_id,
                lead_id=lead.lead_id,
                original_billable_record_id=billable_record.record_id,
                negative_record_id=str(reversal_result.reversal_payload['negative_record_id']),
                created_at=now,
                reason_code=request.dispute_reason_code,
                amount=float(reversal_result.reversal_payload['amount']),
                currency=str(reversal_result.reversal_payload['currency']),
                metadata={'source': 'execute_full_cycle'},
            )
            posting_result = handlers.reversal_posting_service.append_reversal(reversal=reversal, booked_at=now)
            refund_preview = handlers.refund_projection.build_preview(original_record=billable_record, reversal=reversal, user_id=dispute_case.opened_by)
            reversal_payload = {
                **dict(reversal_result.reversal_payload),
                'ledger_posting_id': posting_result.posting.posting_id,
                'status': reversal_result.dispute.status,
                'negative_record_id': None if reversal_result.negative_record is None else reversal_result.negative_record.record_id,
                'refund_preview': refund_preview,
            }
            corrected_revenue = handlers.revenue_control_service.process(
                now=now,
                order=order,
                verified_clients=1 if verification_result.verdict.verified else 0,
                existing_billable_records=(billable_record,),
                new_records=(reversal_result.negative_record,) if reversal_result.negative_record is not None else (),
                acquisition_cost=request.acquisition_cost,
            )
            handlers.lifecycle_service.record_stage(order_id=order.order_id, lead_id=lead.lead_id, stage_name='reversed', now=now, payload=reversal_payload)

    corrected_payload = _revenue_payload(corrected_revenue).model_dump()
    handlers.lifecycle_service.record_stage(order_id=order.order_id, lead_id=lead.lead_id, stage_name='corrected_economics', now=now, payload=corrected_payload)

    summary = handlers.control_plane_service.build_summary(order=order, economic_snapshot=corrected_revenue.economic_snapshot)
    widgets = handlers.control_plane_service.build_widgets(summary=summary)
    admin_summary_payload = {
        'tenant_id': summary.tenant_id,
        'business_id': summary.business_id,
        'order_id': summary.order_id,
        'package_id': summary.package_id,
        'requested_clients': summary.requested_clients,
        'verified_clients': summary.verified_clients,
        'billable_clients': summary.billable_clients,
        'reversed_clients': summary.reversed_clients,
        'open_disputes': summary.open_disputes,
        'reversed_disputes': summary.reversed_disputes,
        'gross_revenue': summary.gross_revenue,
        'net_revenue': summary.net_revenue,
        'currency': summary.currency,
        'widgets': tuple({'widget_id': item.widget_id, 'kind': item.kind, 'payload': item.payload} for item in widgets),
    }
    handlers.commercial_state_service.record_reversal(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        now=now,
        reversal_payload=reversal_payload,
        corrected_revenue_payload=corrected_payload,
        admin_summary_payload=admin_summary_payload,
    )
    refund_preview = None if reversal_payload is None else reversal_payload.get('refund_preview')
    refund_request_payload = None
    refund_request = handlers.refund_request_bridge.to_request(now=now, preview=refund_preview)
    if refund_request is not None:
        refund_request_payload = {
            'tenant_id': refund_request.tenant_id,
            'invoice_id': refund_request.invoice_id,
            'user_id': refund_request.user_id,
            'amount_minor': refund_request.amount_minor,
            'currency': refund_request.currency,
            'reason': refund_request.reason,
            'provider_name': refund_request.provider_name,
            'requested_at': refund_request.requested_at.isoformat(),
            'idempotency_key': refund_request.idempotency_key,
            'metadata': dict(refund_request.metadata),
        }
        handlers.lifecycle_service.record_stage(
            order_id=order.order_id,
            lead_id=lead.lead_id,
            stage_name='refund_requested',
            now=now,
            payload=refund_request_payload,
        )
    handlers.corrected_economics_service.record_snapshot(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        now=now,
        corrected_revenue_payload=corrected_payload,
        reversal_payload=reversal_payload,
        refund_preview=refund_preview,
        refund_request=refund_request_payload,
    )

    response = ExecuteClientOutcomeCycleResponse(
        order=execution_response.order.model_dump(),
        execution=execution_response.execution,
        verification=ClientOutcomeVerificationResponse(
            verified=verification_result.verdict.verified,
            billable=verification_result.verdict.billable,
            reason_code=verification_result.verdict.reason_code,
            confidence=verification_result.verdict.confidence,
            attributed=verification_result.verdict.attribution.attributed,
            fraud_score=verification_result.verdict.fraud.fraud_score,
            eligibility_category=verification_result.verdict.eligibility.category,
            proof_refs=verification_result.verdict.proof_refs,
        ),
        billable_record=None if billable_record is None else _billable_record_payload(billable_record),
        revenue_before_reversal=_revenue_payload(revenue_before),
        dispute=dispute_payload,
        reversal=reversal_payload,
        revenue_after_reversal=_revenue_payload(corrected_revenue),
        admin_summary=admin_summary_payload,
    )
    if request.idempotency_key:
        handlers.cycle_idempotency_service.save_response(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            lead_id=request.lead.lead_id,
            idempotency_key=request.idempotency_key,
            now=now,
            response_payload=response.model_dump(),
        )
    return response
