from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lead_outcomes import OutcomeVerifier
from lead_outcomes.client_attribution_policy import ClientAttributionPolicy
from lead_outcomes.client_eligibility_policy import ClientEligibilityPolicy
from lead_outcomes.client_fraud_policy import ClientFraudPolicy
from lead_outcomes.client_outcome_contract import (
    ClientOutcomeOrder,
    ClientOutcomePackage,
    ClientProofEvent,
    OutcomeLead,
)
from lead_outcomes.client_outcome_registry import ClientOutcomeRegistry
from lead_outcomes.client_outcome_service import ClientOutcomeService
from lead_outcomes.client_verification_service import ClientVerificationService


def test_billable_verified_new_client_flow() -> None:
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    order = ClientOutcomeOrder(
        order_id='order-1',
        business_id='biz-1',
        tenant_id='tenant-1',
        package=ClientOutcomePackage(
            package_id='pkg-10',
            label='10 clients',
            requested_clients=10,
            price_per_verified_client=45.0,
            currency='EUR',
            require_crm_proof=True,
            require_payment_proof=False,
            allow_returning_clients=False,
        ),
        created_at=now - timedelta(days=1),
    )
    lead = OutcomeLead(
        lead_id='lead-1',
        order_id=order.order_id,
        business_id='biz-1',
        tenant_id='tenant-1',
        captured_at=now - timedelta(hours=2),
        tracking_token='trk-1',
        source_channel='ads',
        phone_hash='phone-a',
    )
    proof = ClientProofEvent(
        proof_id='proof-1',
        lead_id='lead-1',
        business_id='biz-1',
        tenant_id='tenant-1',
        occurred_at=now - timedelta(minutes=20),
        proof_type='booking_confirmed',
        status='confirmed',
        source='crm',
        external_ref='crm:deal:1',
    )
    service = ClientOutcomeService(
        registry=ClientOutcomeRegistry(),
        verification_service=ClientVerificationService(
            attribution_policy=ClientAttributionPolicy(),
            fraud_policy=ClientFraudPolicy(),
            eligibility_policy=ClientEligibilityPolicy(),
            outcome_verifier=OutcomeVerifier(),
        ),
    )
    result = service.evaluate_lead(
        now=now,
        order=order,
        lead=lead,
        proofs=(proof,),
        related_leads=(lead,),
        historical_leads=(),
    )
    assert result.verdict.verified is True
    assert result.verdict.billable is True
    assert result.billable_record is not None
    assert result.billable_record.amount == 45.0


def test_returning_client_is_rejected() -> None:
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    order = ClientOutcomeOrder(
        order_id='order-2',
        business_id='biz-1',
        tenant_id='tenant-1',
        package=ClientOutcomePackage(
            package_id='pkg-5',
            label='5 clients',
            requested_clients=5,
            price_per_verified_client=50.0,
            currency='EUR',
            require_crm_proof=True,
            allow_returning_clients=False,
            new_client_window_days=180,
        ),
        created_at=now - timedelta(days=1),
    )
    current_lead = OutcomeLead(
        lead_id='lead-new',
        order_id=order.order_id,
        business_id='biz-1',
        tenant_id='tenant-1',
        captured_at=now - timedelta(hours=1),
        tracking_token='trk-2',
        source_channel='ads',
        phone_hash='same-phone',
    )
    old_lead = OutcomeLead(
        lead_id='lead-old',
        order_id='old-order',
        business_id='biz-1',
        tenant_id='tenant-1',
        captured_at=now - timedelta(days=10),
        tracking_token='trk-old',
        source_channel='organic',
        phone_hash='same-phone',
    )
    proof = ClientProofEvent(
        proof_id='proof-2',
        lead_id='lead-new',
        business_id='biz-1',
        tenant_id='tenant-1',
        occurred_at=now - timedelta(minutes=30),
        proof_type='crm_won',
        status='won',
        source='crm',
        external_ref='crm:deal:2',
    )
    service = ClientOutcomeService(
        registry=ClientOutcomeRegistry(),
        verification_service=ClientVerificationService(
            attribution_policy=ClientAttributionPolicy(),
            fraud_policy=ClientFraudPolicy(),
            eligibility_policy=ClientEligibilityPolicy(),
            outcome_verifier=OutcomeVerifier(),
        ),
    )
    result = service.evaluate_lead(
        now=now,
        order=order,
        lead=current_lead,
        proofs=(proof,),
        related_leads=(current_lead, old_lead),
        historical_leads=(old_lead,),
    )
    assert result.verdict.billable is False
    assert result.verdict.eligibility.reason_code == 'returning_client_blocked'
