from __future__ import annotations

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from entrypoints.api.client_outcome_cycle_models import ClientOutcomeVerificationResponse, ExecuteClientOutcomeCycleResponse
from entrypoints.api.client_outcome_routes.module_helpers import _billable_record_payload, _revenue_payload


def complete_full_cycle(
    handlers,
    *,
    now,
    request,
    request_payload,
    idempotency_lease_token,
    execution_response,
    order,
    lead,
    verification_result,
    billable_record,
    revenue_before,
):
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
        handlers.lifecycle_service.record_stage(
            order_id=order.order_id,
            lead_id=lead.lead_id,
            stage_name='dispute_opened',
            now=now,
            payload=dispute_payload,
        )
        handlers.commercial_state_service.record_dispute(
            order_id=order.order_id,
            lead_id=lead.lead_id,
            now=now,
            dispute_payload=dispute_payload,
        )
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
            refund_preview = handlers.refund_projection.build_preview(
                original_record=billable_record,
                reversal=reversal,
                user_id=dispute_case.opened_by,
            )
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
            handlers.lifecycle_service.record_stage(
                order_id=order.order_id,
                lead_id=lead.lead_id,
                stage_name='reversed',
                now=now,
                payload=reversal_payload,
            )

    corrected_payload = _revenue_payload(corrected_revenue).model_dump()
    handlers.lifecycle_service.record_stage(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        stage_name='corrected_economics',
        now=now,
        payload=corrected_payload,
    )

    summary = handlers.control_plane_service.build_summary(
        order=order,
        economic_snapshot=corrected_revenue.economic_snapshot,
    )
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
        if not idempotency_lease_token:
            raise RuntimeError('client_outcome_idempotency_lease_token_missing')
        handlers.cycle_idempotency_service.complete(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            lead_id=request.lead.lead_id,
            idempotency_key=request.idempotency_key,
            lease_token=idempotency_lease_token,
            now=now,
            request_payload=request_payload,
            response_payload=response.model_dump(mode='json'),
        )
    return response


__all__ = ['complete_full_cycle']
