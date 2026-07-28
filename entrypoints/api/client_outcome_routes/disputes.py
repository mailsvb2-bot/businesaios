from __future__ import annotations

from datetime import datetime

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from entrypoints.api.client_outcome_dispute_models import (
    ClientOutcomeDisputeResponse,
    ClientOutcomeReversalResponse,
    OpenClientOutcomeDisputeRequest,
    ReverseClientOutcomeDisputeRequest,
)
from entrypoints.api.client_outcome_routes.module_helpers import _billable_record_from_input, _require_order_tenant


def open_dispute(handlers, *, now: datetime, request: OpenClientOutcomeDisputeRequest, tenant_id: str) -> ClientOutcomeDisputeResponse:
    order = _require_order_tenant(handlers, order_id=request.order_id, tenant_id=tenant_id)
    record = _billable_record_from_input(request.record)
    expected = (str(tenant_id), str(order.business_id), str(order.order_id), str(request.lead_id))
    actual = (str(request.tenant_id), str(request.business_id), str(request.order_id), str(record.lead_id))
    record_scope = (str(record.tenant_id), str(record.business_id), str(record.order_id), str(record.lead_id))
    if actual != expected or record_scope != expected:
        raise PermissionError('client_outcome_dispute_scope_mismatch')
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


def reverse_dispute(handlers, *, now: datetime, request: ReverseClientOutcomeDisputeRequest, tenant_id: str) -> ClientOutcomeReversalResponse:
    case = handlers.dispute_service.get_case(request.dispute_id)
    if case is None:
        raise KeyError(request.dispute_id)
    _require_order_tenant(handlers, order_id=case.order_id, tenant_id=tenant_id)
    if str(case.tenant_id).strip() != str(tenant_id).strip():
        raise PermissionError('client_outcome_dispute_tenant_mismatch')
    original_record = _billable_record_from_input(request.record)
    case_scope = (
        str(case.tenant_id), str(case.business_id), str(case.order_id), str(case.lead_id), str(case.billable_record_id)
    )
    record_scope = (
        str(original_record.tenant_id), str(original_record.business_id), str(original_record.order_id),
        str(original_record.lead_id), str(original_record.record_id)
    )
    if record_scope != case_scope:
        raise PermissionError('client_outcome_reversal_scope_mismatch')
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
    refund_preview = handlers.refund_projection.build_preview(
        original_record=original_record,
        reversal=reversal,
        user_id=case.opened_by,
    )
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
