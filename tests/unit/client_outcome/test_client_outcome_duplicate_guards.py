from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from billing.client_outcome_dispute_service import ClientOutcomeDisputeService
from billing.client_outcome_dispute_store import ClientOutcomeDisputeStore, ClientOutcomeReversalStore
from billing.client_outcome_negative_usage_builder import ClientOutcomeNegativeUsageBuilder
from billing.client_outcome_refund_window_policy import ClientOutcomeRefundWindowPolicy
from lead_outcomes.client_outcome_contract import BillableClientRecord
from registry.base_registry import BaseRegistry


def _service() -> ClientOutcomeDisputeService:
    return ClientOutcomeDisputeService(
        dispute_store=ClientOutcomeDisputeStore(),
        reversal_store=ClientOutcomeReversalStore(registry=BaseRegistry(kind='client_outcome_reversal')),
        refund_window_policy=ClientOutcomeRefundWindowPolicy(refund_window_days=14),
        negative_usage_builder=ClientOutcomeNegativeUsageBuilder(),
    )


def test_duplicate_open_dispute_reuses_same_case() -> None:
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)
    service = _service()
    record = BillableClientRecord(
        record_id='billable:1', tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
        package_id='clients-5', verified_at=now - timedelta(days=1), unit_price=70.0, currency='EUR',
        metadata={'invoice_id': 'inv-1', 'provider_name': 'stripe'}
    )
    first = service.open_dispute(
        now=now, tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
        billable_record_id='billable:1', opened_by='u1', reason_code='duplicate_client', record=record,
    )
    second = service.open_dispute(
        now=now, tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
        billable_record_id='billable:1', opened_by='u1', reason_code='duplicate_client', record=record,
    )
    assert second.dispute_id == first.dispute_id


def test_duplicate_reverse_reuses_existing_reversal_payload() -> None:
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)
    service = _service()
    record = BillableClientRecord(
        record_id='billable:1', tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
        package_id='clients-5', verified_at=now - timedelta(days=1), unit_price=70.0, currency='EUR'
    )
    case = service.open_dispute(
        now=now, tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
        billable_record_id='billable:1', opened_by='u1', reason_code='duplicate_client', record=record,
    )
    first = service.accept_and_reverse(now=now, case=case, original_record=record, reversal_amount=35.0)
    second = service.accept_and_reverse(now=now, case=case, original_record=record, reversal_amount=35.0)
    assert first.reversal_payload is not None
    assert second.reversal_payload is not None
    assert second.reversal_payload['reversal_id'] == first.reversal_payload['reversal_id']
    assert bool(second.reversal_payload.get('replayed_reversal')) is True
