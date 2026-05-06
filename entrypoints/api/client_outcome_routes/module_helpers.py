from __future__ import annotations

from datetime import datetime

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from billing.client_outcome_revenue_control_service import ClientOutcomeRevenueControlService
from entrypoints.api.client_outcome_cycle_models import ClientOutcomeRevenueResponse
from entrypoints.api.client_outcome_dispute_models import ClientOutcomeBillableRecordInput
from entrypoints.api.client_outcome_models import ClientOutcomeOrderResponse
from lead_outcomes.client_outcome_contract import BillableClientRecord, ClientOutcomeOrder, ClientOutcomePackage


def _present_order(order: ClientOutcomeOrder) -> ClientOutcomeOrderResponse:
    return ClientOutcomeOrderResponse(
        order_id=order.order_id,
        tenant_id=order.tenant_id,
        business_id=order.business_id,
        package_id=order.package.package_id,
        package_label=order.package.label,
        requested_clients=order.package.requested_clients,
        price_per_verified_client=order.package.price_per_verified_client,
        currency=order.package.currency,
        trust_tier=order.package.trust_tier,
        created_at=order.created_at.isoformat(),
    )


def _merge_billable_record_metadata(record: BillableClientRecord, *metadata_sources: object) -> BillableClientRecord:
    merged = record.normalized_metadata()
    for source in metadata_sources:
        if isinstance(source, dict):
            for key, value in source.items():
                if key not in merged and value not in (None, ''):
                    merged[key] = value
    return BillableClientRecord(
        record_id=record.record_id,
        tenant_id=record.tenant_id,
        business_id=record.business_id,
        order_id=record.order_id,
        lead_id=record.lead_id,
        package_id=record.package_id,
        verified_at=record.verified_at,
        unit_price=record.unit_price,
        currency=record.currency,
        quantity=record.quantity,
        metadata=merged,
    )


def _billable_record_payload(record: BillableClientRecord) -> dict[str, object]:
    return {
        'record_id': record.record_id,
        'tenant_id': record.tenant_id,
        'business_id': record.business_id,
        'order_id': record.order_id,
        'lead_id': record.lead_id,
        'package_id': record.package_id,
        'verified_at': record.verified_at.isoformat(),
        'unit_price': record.unit_price,
        'currency': record.currency,
        'quantity': record.quantity,
        'amount': record.amount,
        'metadata': dict(record.metadata),
    }


def _revenue_payload(result: ClientOutcomeRevenueControlService | object) -> ClientOutcomeRevenueResponse:
    snapshot = result.economic_snapshot
    return ClientOutcomeRevenueResponse(
        appended_record_ids=tuple(result.appended_record_ids),
        rejected_record_ids=tuple(result.rejected_record_ids),
        invoice_line_ids=tuple(result.invoice_line_ids),
        billable_clients=result.billable_clients,
        verified_clients=result.verified_clients,
        billed_revenue=snapshot.billed_revenue,
        acquisition_cost=snapshot.acquisition_cost,
        gross_margin=snapshot.gross_margin,
        cac=snapshot.cac,
        revenue_per_client=snapshot.revenue_per_client,
        margin_per_client=snapshot.margin_per_client,
        currency=snapshot.currency,
    )


def _order_from_response(order_response: ClientOutcomeOrderResponse) -> ClientOutcomeOrder:
    return _order_from_input(order_response)


def _billable_record_from_input(record: ClientOutcomeBillableRecordInput) -> BillableClientRecord:
    return BillableClientRecord(
        record_id=record.record_id,
        tenant_id=record.tenant_id,
        business_id=record.business_id,
        order_id=record.order_id,
        lead_id=record.lead_id,
        package_id=record.package_id,
        verified_at=datetime.fromisoformat(record.verified_at),
        unit_price=record.unit_price,
        currency=record.currency,
        quantity=record.quantity,
        metadata=record.metadata,
    )


def _order_from_input(order) -> ClientOutcomeOrder:
    return ClientOutcomeOrder(
        order_id=order.order_id,
        tenant_id=order.tenant_id,
        business_id=order.business_id,
        package=ClientOutcomePackage(
            package_id=order.package_id,
            label=order.package_label,
            requested_clients=order.requested_clients,
            price_per_verified_client=order.price_per_verified_client,
            currency=order.currency,
            trust_tier=order.trust_tier,
        ).normalized_copy(),
        created_at=datetime.fromisoformat(order.created_at),
        metadata={},
    )
