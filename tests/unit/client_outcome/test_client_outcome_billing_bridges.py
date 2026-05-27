from __future__ import annotations

from datetime import datetime, timedelta, timezone

from billing.client_outcome_dispute_classification_bridge import ClientOutcomeDisputeClassificationBridge
from billing.client_outcome_dispute_service import ClientOutcomeDisputeService
from billing.client_outcome_dispute_store import ClientOutcomeDisputeStore, ClientOutcomeReversalStore
from billing.client_outcome_negative_usage_builder import ClientOutcomeNegativeUsageBuilder
from billing.client_outcome_refund_window_policy import ClientOutcomeRefundWindowPolicy
from billing.client_outcome_reversal_ledger_bridge import ClientOutcomeReversalLedgerBridge
from billing.dispute_policy import DisputePolicy
from lead_outcomes.client_outcome_contract import BillableClientRecord
from registry.base_registry import BaseRegistry


def test_dispute_classification_bridge_maps_duplicate_client() -> None:
    record = BillableClientRecord(
        record_id='billable:1', tenant_id='tenant-1', business_id='biz-1', order_id='order-1',
        lead_id='lead-1', package_id='clients-5', verified_at=datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc),
        unit_price=70.0, currency='EUR'
    )
    bridge = ClientOutcomeDisputeClassificationBridge(dispute_policy=DisputePolicy())
    classification = bridge.classify(reason_code='duplicate_client', record=record)
    payload = bridge.build_payload(reason_code='duplicate_client', record=record)

    assert classification.case_type == 'existing_customer_challenge'
    assert classification.severity == 'medium'
    assert payload['duplicate_flag'] is True
    assert payload['existing_customer_flag'] is True
    assert payload['evidence_fingerprint']


def test_open_dispute_enriches_metadata_with_classification() -> None:
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc)
    record = BillableClientRecord(
        record_id='billable:1', tenant_id='tenant-1', business_id='biz-1', order_id='order-1',
        lead_id='lead-1', package_id='clients-5', verified_at=now - timedelta(days=1),
        unit_price=70.0, currency='EUR'
    )
    service = ClientOutcomeDisputeService(
        dispute_store=ClientOutcomeDisputeStore(),
        reversal_store=ClientOutcomeReversalStore(registry=BaseRegistry(kind='client_outcome_reversal')),
        refund_window_policy=ClientOutcomeRefundWindowPolicy(refund_window_days=14),
        negative_usage_builder=ClientOutcomeNegativeUsageBuilder(),
    )
    case = service.open_dispute(
        now=now,
        tenant_id='tenant-1',
        business_id='biz-1',
        order_id='order-1',
        lead_id='lead-1',
        billable_record_id='billable:1',
        opened_by='owner-1',
        reason_code='missing_proof',
        record=record,
    )
    assert case.metadata['classification_case_type'] == 'evidence_gap_review'
    assert case.metadata['classification_severity'] == 'medium'
    assert case.metadata['evidence_fingerprint']


def test_reversal_ledger_bridge_builds_balanced_posting() -> None:
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc)
    record = BillableClientRecord(
        record_id='billable:1', tenant_id='tenant-1', business_id='biz-1', order_id='order-1',
        lead_id='lead-1', package_id='clients-5', verified_at=now - timedelta(days=1),
        unit_price=70.0, currency='EUR'
    )
    service = ClientOutcomeDisputeService(
        dispute_store=ClientOutcomeDisputeStore(),
        reversal_store=ClientOutcomeReversalStore(registry=BaseRegistry(kind='client_outcome_reversal')),
        refund_window_policy=ClientOutcomeRefundWindowPolicy(refund_window_days=14),
        negative_usage_builder=ClientOutcomeNegativeUsageBuilder(),
    )
    case = service.open_dispute(
        now=now,
        tenant_id='tenant-1',
        business_id='biz-1',
        order_id='order-1',
        lead_id='lead-1',
        billable_record_id='billable:1',
        opened_by='owner-1',
        reason_code='duplicate_client',
        record=record,
    )
    resolution = service.accept_and_reverse(now=now, case=case, original_record=record)
    reversal_payload = service.list_order_reversals(tenant_id='tenant-1', order_id='order-1')[0]
    reversal_bridge = ClientOutcomeReversalLedgerBridge()
    posting = reversal_bridge.build_posting(
        reversal=__import__('billing.client_outcome_reversal_contract', fromlist=['ClientOutcomeReversalRecord']).ClientOutcomeReversalRecord(
            reversal_id=reversal_payload['reversal_id'], tenant_id='tenant-1', business_id='biz-1', order_id='order-1', lead_id='lead-1',
            original_billable_record_id='billable:1', negative_record_id=reversal_payload['negative_record_id'],
            created_at=now, reason_code='duplicate_client', amount=reversal_payload['amount'], currency='EUR'
        ),
        booked_at=now,
    )
    assert resolution.negative_record is not None
    assert len(posting.entries) == 2
    assert sum(e.amount_minor for e in posting.entries if e.side == 'debit') == 7000
    assert sum(e.amount_minor for e in posting.entries if e.side == 'credit') == 7000
