"""Real owner registries and a controlled PSP authority: settlement, fraud, replay."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_checkout import CommercialCheckoutCoordinator
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from billing.phase18_commercial_settlement import (
    CommercialSettlementReconciler,
    ProviderSettlementEvidence,
)
from contracts.customer import Customer, CustomerRecord
from core.offers.offer_types import OfferSummary
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from billing.payment_provider_contract import PaymentCheckoutSession


class Customers:
    def get_customer(self, *, tenant_id, business_id, customer_id):
        return CustomerRecord(customer=Customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        ))


class Offers:
    def resolve(self, *, key):
        return SimpleNamespace(
            id="trusted-catalog", list_offers=lambda: [OfferSummary(
                offer_id="course", title="Published course", base_price_rub=890,
                meta={"program_id": key.product_id, "business_id": key.business_id},
            )],
        )


class SandboxCheckout:
    def create_checkout(self, request):
        return PaymentCheckoutSession(
            tenant_id=request.tenant_id, provider_name="sandbox",
            external_reference="ref-1", checkout_url="https://sandbox.example/pay/ref-1",
            status="pending", amount_minor=request.amount_minor, currency=request.currency,
        )


class VerifiedSandboxAuthority:
    def __init__(self, proof):
        self.proof = proof
        self.calls = 0

    def fetch_settlement_evidence(self, **kwargs):
        self.calls += 1
        assert kwargs["provider_name"] == "sandbox"
        assert kwargs["external_reference"] == "ref-1"
        return self.proof


def build():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    leads.create(**scope, lead_id="lead-a", customer_id="customer-a",
                 conversation_id="conversation-a", channel="telegram",
                 idempotency_key="new-lead", status="new", source="telegram")
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    program = programs.publish(
        access_mode="paid",
        **scope, actor_id="owner-a", title="Published course",
        lessons=[{"title": "Lesson 1", "content_kind": "text", "content_ref": "First lesson"}],
        idempotency_key="program-a",
    )
    invoices = InvoiceRegistry(event_store=events, idempotency_store=claims)
    purchases = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs, offers=Offers(),
        orders=OrderStore(event_store=events), invoices=invoices,
    )
    order = purchases.prepare_purchase(
        **scope, lead_id="lead-a", customer_id="customer-a", program_id=program["id"],
        offer_id="course", idempotency_key="buyer-one",
    )
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchases, payment_adapter=SandboxCheckout(),
        event_store=events, idempotency_store=claims,
    )
    session = checkout.open_checkout(**scope, order_id=order.order_id)
    proof = ProviderSettlementEvidence(
        provider_name=session.provider_name,
        merchant_id="trusted-merchant",
        external_reference=session.external_reference,
        order_id=order.order_id, invoice_id=order.invoice_id,
        **scope, currency=order.currency,
        amount_minor=order.amount_minor, status="succeeded",
        evidence_id="verified-psp-evidence-1",
    )
    authority = VerifiedSandboxAuthority(proof)
    reconciler = CommercialSettlementReconciler(
        purchases=purchases, checkouts=checkout,
        payment_verifier=authority,
        configured_merchant_id="trusted-merchant",
    )
    return locals()


def test_verified_psp_posts_once_into_canonical_invoice_and_survives_reread():
    env = build()
    scope = env["scope"]
    order = env["order"]
    reconciler = env["reconciler"]
    invoice = env["invoices"]
    assert invoice.get(**scope, invoice_id=order.invoice_id).status.value == "issued"
    result = reconciler.reconcile(**scope, order_id=order.order_id)
    assert result.provider_verified is True
    assert result.billing_status == "paid"
    assert result.total_minor == result.paid_minor == 89000
    assert reconciler.reconcile(**scope, order_id=order.order_id) == result
    restored = InvoiceRegistry(event_store=env["events"], idempotency_store=env["claims"])
    assert restored.get(**scope, invoice_id=order.invoice_id).paid_minor == 89000
    assert restored.has_verified_psp_payment_evidence(
        **scope, invoice_id=order.invoice_id, evidence_id="verified-psp-evidence-1",
    ) is True
    events = [event for event in env["events"]
              if (event.get("payload") or {}).get("fact_type") == "invoice.payment_recorded"]
    assert len(events) == 1
    fact = events[0]
    assert fact["payload"]["evidence_ids"] == ["verified-psp-evidence-1"]
    assert fact["payload"]["provenance"]["authority"] == "verified_psp"


@pytest.mark.parametrize("changes", [
    {"amount_minor": 89001}, {"amount_minor": 0},
    {"currency": "USD"}, {"merchant_id": "attacker-merchant"},
    {"provider_name": "attacker"}, {"external_reference": "stolen-payment"},
    {"order_id": "other-order"}, {"invoice_id": "other-invoice"},
    {"business_id": "business-b"}, {"tenant_id": "tenant-b"},
])
def test_mismatched_provider_evidence_never_creates_paid_fact(changes):
    env = build()
    env["authority"].proof = replace(env["authority"].proof, **changes)
    with pytest.raises(RuntimeError, match="commercial_settlement_provider_provenance_invalid"):
        env["reconciler"].reconcile(**env["scope"], order_id=env["order"].order_id)
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).paid_minor == 0


@pytest.mark.parametrize("status", [
    "pending", "waiting_for_capture", "canceled", "refunded", "",
    "SUCCEEDED", "paid", "success", "not_succeeded",
])
def test_non_final_provider_state_does_not_mutate_billing(status):
    env = build()
    env["authority"].proof = replace(env["authority"].proof, status=status)
    outcome = env["reconciler"].reconcile(**env["scope"], order_id=env["order"].order_id)
    assert outcome.provider_verified is False
    assert outcome.billing_status == "issued"
    assert outcome.paid_minor == 0
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).status.value == "issued"


def test_failed_authority_and_cross_business_read_fail_closed():
    env = build()
    env["authority"].proof = None
    with pytest.raises(RuntimeError, match="commercial_settlement_authoritative_evidence_invalid"):
        env["reconciler"].reconcile(**env["scope"], order_id=env["order"].order_id)
    with pytest.raises(LookupError):
        env["reconciler"].reconcile(
            tenant_id="tenant-a", business_id="business-b", order_id=env["order"].order_id,
        )
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).paid_minor == 0



def test_already_paid_invoice_without_matching_psp_proof_cannot_be_laundered():
    env = build()
    scope = env["scope"]
    order = env["order"]
    env["invoices"].record_payment(
        **scope, invoice_id=order.invoice_id,
        idempotency_key="manually-paid-without-psp", amount_minor=order.amount_minor,
    )
    with pytest.raises(RuntimeError, match="commercial_settlement_paid_without_matching_proof"):
        env["reconciler"].reconcile(**scope, order_id=order.order_id)
    assert env["invoices"].has_verified_psp_payment_evidence(
        **scope, invoice_id=order.invoice_id, evidence_id="verified-psp-evidence-1",
    ) is False


def test_second_psp_evidence_cannot_replace_the_proof_that_paid_an_invoice():
    env = build()
    scope, order = env["scope"], env["order"]
    first = env["reconciler"].reconcile(**scope, order_id=order.order_id)
    env["authority"].proof = replace(env["authority"].proof, evidence_id="second-psp-evidence")

    with pytest.raises(RuntimeError, match="commercial_settlement_paid_without_matching_proof"):
        env["reconciler"].reconcile(**scope, order_id=order.order_id)

    paid_events = [
        event for event in env["events"]
        if (event.get("payload") or {}).get("fact_type") == "invoice.payment_recorded"
    ]
    assert first.provider_verified is True
    assert len(paid_events) == 1
    assert env["invoices"].get(**scope, invoice_id=order.invoice_id).paid_minor == order.amount_minor


def test_parallel_psp_confirms_post_exactly_once():
    from threading import Barrier, Thread

    env = build()
    scope, order = env["scope"], env["order"]
    outcomes = []
    errors = []
    evidence_barrier = Barrier(8)
    authority = env["authority"]
    fetch_evidence = authority.fetch_settlement_evidence

    def synchronized_evidence(**kwargs):
        proof = fetch_evidence(**kwargs)
        # Every worker has already read the same unpaid invoice before any
        # worker is allowed to enter the canonical invoice transition.
        evidence_barrier.wait(timeout=10)
        return proof

    authority.fetch_settlement_evidence = synchronized_evidence

    def reconcile():
        try:
            outcomes.append(env["reconciler"].reconcile(**scope, order_id=order.order_id))
        except Exception as exc:  # noqa: BLE001 - assert the exact controlled race below
            errors.append(exc)

    threads = [Thread(target=reconcile) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert all(not thread.is_alive() for thread in threads)
    assert authority.calls == len(threads)
    assert len(outcomes) + len(errors) == len(threads)
    assert all(
        type(error) is RuntimeError
        and str(error) == "ontology transition rejected: in_progress"
        for error in errors
    )
    assert outcomes

    paid_events = [
        event for event in env["events"]
        if (event.get("payload") or {}).get("fact_type") == "invoice.payment_recorded"
    ]
    assert len(paid_events) == 1
    assert env["invoices"].get(**scope, invoice_id=order.invoice_id).paid_minor == order.amount_minor


@pytest.mark.parametrize("amount_minor", [True, "89000", 89000.0, -89000, 0])
def test_non_integer_or_nonpositive_provider_amount_never_posts(amount_minor):
    env = build()
    env["authority"].proof = replace(env["authority"].proof, amount_minor=amount_minor)
    with pytest.raises(RuntimeError, match="commercial_settlement_provider_provenance_invalid"):
        env["reconciler"].reconcile(**env["scope"], order_id=env["order"].order_id)
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).paid_minor == 0


@pytest.mark.parametrize("evidence_id", ["", "x" * 257])
def test_missing_or_oversized_provider_evidence_id_never_posts(evidence_id):
    env = build()
    env["authority"].proof = replace(env["authority"].proof, evidence_id=evidence_id)
    with pytest.raises(RuntimeError, match="commercial_settlement_provider_provenance_invalid"):
        env["reconciler"].reconcile(**env["scope"], order_id=env["order"].order_id)
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).paid_minor == 0


def test_foreign_tenant_cannot_reconcile_or_read_the_order():
    env = build()
    with pytest.raises(LookupError):
        env["reconciler"].reconcile(
            tenant_id="tenant-b", business_id="business-a", order_id=env["order"].order_id,
        )
    assert env["authority"].calls == 0
    assert env["invoices"].get(**env["scope"], invoice_id=env["order"].invoice_id).paid_minor == 0


def test_unknown_order_never_reaches_the_payment_authority():
    env = build()
    with pytest.raises(LookupError):
        env["reconciler"].reconcile(**env["scope"], order_id="missing-order")
    assert env["authority"].calls == 0
