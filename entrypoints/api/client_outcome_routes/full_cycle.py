from __future__ import annotations

from datetime import datetime

from entrypoints.api.client_outcome_cycle_models import ExecuteClientOutcomeCycleRequest, ExecuteClientOutcomeCycleResponse
from entrypoints.api.client_outcome_models import SelectClientOutcomePackageRequest
from entrypoints.api.client_outcome_routes.full_cycle_completion import complete_full_cycle
from entrypoints.api.client_outcome_routes.module_helpers import (
    _billable_record_payload,
    _merge_billable_record_metadata,
    _order_from_response,
    _revenue_payload,
)
from lead_outcomes.client_outcome_contract import ClientProofEvent, OutcomeLead


def execute_full_cycle(
    handlers,
    *,
    now: datetime,
    request: ExecuteClientOutcomeCycleRequest,
    tenant_id: str,
) -> ExecuteClientOutcomeCycleResponse:
    if str(request.tenant_id).strip() != str(tenant_id).strip():
        raise PermissionError('client_outcome_cycle_tenant_mismatch')
    request_payload = request.model_dump(mode='json')
    idempotency_lease_token: str | None = None
    if request.idempotency_key:
        reservation = handlers.cycle_idempotency_service.reserve(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            lead_id=request.lead.lead_id,
            idempotency_key=request.idempotency_key,
            now=now,
            request_payload=request_payload,
        )
        if reservation.get('response') is not None:
            return ExecuteClientOutcomeCycleResponse(**dict(reservation['response']))
        idempotency_lease_token = str(reservation.get('lease_token') or '').strip()
        if not idempotency_lease_token:
            raise RuntimeError('client_outcome_idempotency_lease_token_missing')

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
    handlers.lifecycle_service.record_stage(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        stage_name='verified',
        now=now,
        payload=verification_payload,
    )
    handlers.commercial_state_service.record_verification(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        now=now,
        payload=verification_payload,
    )

    revenue_before = handlers.revenue_control_service.process(
        now=now,
        order=order,
        verified_clients=1 if verification_result.verdict.verified else 0,
        existing_billable_records=(),
        new_records=() if billable_record is None else (billable_record,),
        acquisition_cost=request.acquisition_cost,
    )
    handlers.lifecycle_service.record_stage(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        stage_name='billed',
        now=now,
        payload=_revenue_payload(revenue_before).model_dump(),
    )
    handlers.commercial_state_service.record_billing(
        order_id=order.order_id,
        lead_id=lead.lead_id,
        now=now,
        billable_record=None if billable_record is None else _billable_record_payload(billable_record),
        revenue_payload=_revenue_payload(revenue_before).model_dump(),
    )

    return complete_full_cycle(
        handlers,
        now=now,
        request=request,
        request_payload=request_payload,
        idempotency_lease_token=idempotency_lease_token,
        execution_response=execution_response,
        order=order,
        lead=lead,
        verification_result=verification_result,
        billable_record=billable_record,
        revenue_before=revenue_before,
    )
