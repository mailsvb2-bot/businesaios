"""Sale -> real canonical PSP evidence -> paid enrollment -> revocation, no fake success."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_commercial_routes import register_business_workspace_commercial_routes
from application.commerce.phase18_commercial_access import CanonicalPaidProgramAccess
from application.commerce.phase18_commercial_checkout import CommercialCheckoutCoordinator
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from billing.payment_provider_contract import PaymentCheckoutSession
from billing.phase18_commercial_settlement import CommercialSettlementReconciler, ProviderSettlementEvidence
from core.offers.offer_types import OfferSummary
from crm.customer_registry import CustomerRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


class CanonicalOrderBackendFixture:
    """Same durable-backend contract survives recreation of OrderStore."""
    def __init__(self):
        self.rows = {}

    def replace(self, key, value):
        self.rows[key] = value

    def register_unique(self, key, value):
        if key in self.rows:
            raise ValueError("duplicate")
        self.rows[key] = value

    def get(self, key):
        return self.rows[key]

    def maybe_get(self, key):
        return self.rows.get(key)

    def items(self):
        return tuple(self.rows.items())


class Catalog:
    def resolve(self, *, key):
        return SimpleNamespace(
            id="canonical-offer-catalog",
            list_offers=lambda: [OfferSummary(
                offer_id="course", title="Paid training",
                base_price_rub=1200, meta={
                    "program_id": key.product_id, "business_id": key.business_id,
                },
            )],
        )


class SandboxCheckout:
    def __init__(self):
        self.calls = 0

    def create_checkout(self, request):
        self.calls += 1
        return PaymentCheckoutSession(
            tenant_id=request.tenant_id, provider_name="sandbox",
            external_reference="merchant-payment-1",
            checkout_url="https://sandbox.example/checkout/payment-1",
            status="pending", amount_minor=request.amount_minor, currency=request.currency,
        )


class ServerSettlementVerifier:
    def __init__(self, evidence):
        self.evidence = evidence

    def fetch_settlement_evidence(self, **scope):
        assert scope["provider_name"] == "sandbox"
        assert scope["external_reference"] == "merchant-payment-1"
        return self.evidence


def environment():
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=idem, pii_vault=InMemorySecretVault(),
    )
    customer = customers.ensure_customer_identity(
        **scope, channel="telegram", external_subject="paid-buyer-1",
    ).customer
    programs = ProgramPublicationRegistry(
        event_store=events, idempotency_store=idem, customer_registry=customers,
    )
    program = programs.publish(
        **scope, actor_id="owner-a", title="Paid training",
        lessons=[{"title": "Introduction", "content_kind": "text", "content_ref": "Lesson text"}],
        access_mode="paid", idempotency_key="paid-training-a",
    )
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    leads.create(
        **scope, lead_id="lead-one", idempotency_key="lead-one",
        customer_id=customer.customer_id, conversation_id="conversation-one",
        channel="telegram",
    )
    order_backend = CanonicalOrderBackendFixture()
    orders = OrderStore(event_store=events, backend=order_backend)
    invoices = InvoiceRegistry(event_store=events, idempotency_store=idem)
    purchases = CommercialProgramPurchaseService(
        leads=leads, customers=customers, programs=programs,
        offers=Catalog(), orders=orders, invoices=invoices,
    )
    order = purchases.prepare_purchase(
        **scope, lead_id="lead-one", customer_id=customer.customer_id,
        program_id=program["id"], offer_id="course", idempotency_key="buyer-one",
    )
    psp = SandboxCheckout()
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchases, payment_adapter=psp,
        event_store=events, idempotency_store=idem,
    )
    session = checkout.open_checkout(**scope, order_id=order.order_id)
    evidence = ProviderSettlementEvidence(
        provider_name="sandbox", merchant_id="merchant-one",
        external_reference=session.external_reference, order_id=order.order_id,
        invoice_id=order.invoice_id, **scope, currency=order.currency,
        amount_minor=order.amount_minor, status="succeeded", evidence_id="psp-proof-one",
    )
    verifier = ServerSettlementVerifier(evidence)
    settlement = CommercialSettlementReconciler(
        purchases=purchases, checkouts=checkout, payment_verifier=verifier,
        configured_merchant_id="merchant-one",
    )
    reversal = {"reversed": False, "available": True}

    def reversal_reader(**_):
        if not reversal["available"]:
            raise RuntimeError("commercial_reversal_authority_unavailable")
        return reversal["reversed"]

    paid_access = CanonicalPaidProgramAccess(
        purchases=purchases, checkouts=checkout, reversal_reader=reversal_reader,
    )
    programs.bind_paid_access_authority(paid_access)
    return SimpleNamespace(**locals())


def test_whole_sale_paid_program_access_durable_replay_and_live_revocation():
    e = environment()
    scope, p, order, cid = e.scope, e.program, e.order, e.customer.customer_id
    assert e.psp.calls == 1
    assert e.paid_access.require_access(**scope, program_id=p["id"], customer_id=cid) is False
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        e.programs.enroll_customer(
            **scope, actor_id="owner-a", program_id=p["id"], customer_id=cid,
        )
    assert e.programs.list_enrollments(**scope, program_id=p["id"]) == []
    settled = e.settlement.reconcile(**scope, order_id=order.order_id)
    assert settled.provider_verified is True
    assert settled.billing_status == "paid"
    assert e.settlement.reconcile(**scope, order_id=order.order_id) == settled
    assert e.paid_access.require_access(**scope, program_id=p["id"], customer_id=cid) is True
    enrollment = e.programs.enroll_customer(
        **scope, actor_id="owner-a", program_id=p["id"], customer_id=cid,
    )
    assert enrollment["status"] == "awaiting_delivery"
    assert e.programs.enroll_customer(
        **scope, actor_id="owner-a", program_id=p["id"], customer_id=cid,
    ) == enrollment
    draft = e.programs.lesson_send_plan(
        **scope, program_id=p["id"], enrollment_id=enrollment["id"],
        lesson_position=1, channel="telegram",
    )
    assert draft["execution_allowed"] is False
    assert len([x for x in e.events if (x.get("payload") or {}).get("fact_type") ==
                "invoice.payment_recorded"]) == 1

    # Re-create read owners from the same canonical event spine, not a local grant.
    restored_invoices = InvoiceRegistry(event_store=e.events, idempotency_store=e.idem)
    restored_orders = OrderStore(event_store=e.events, backend=e.order_backend)
    restored_purchases = CommercialProgramPurchaseService(
        leads=e.leads, customers=e.customers, programs=e.programs,
        offers=Catalog(), orders=restored_orders, invoices=restored_invoices,
    )
    restored_checkout = CommercialCheckoutCoordinator(
        purchase_service=restored_purchases, payment_adapter=e.psp,
        event_store=e.events, idempotency_store=e.idem,
    )
    restored_access = CanonicalPaidProgramAccess(
        purchases=restored_purchases, checkouts=restored_checkout,
        reversal_reader=e.reversal_reader,
    )
    assert restored_access.require_access(**scope, program_id=p["id"], customer_id=cid)

    e.reversal["reversed"] = True
    assert not e.paid_access.require_access(**scope, program_id=p["id"], customer_id=cid)
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        e.programs.lesson_send_plan(
            **scope, program_id=p["id"], enrollment_id=enrollment["id"],
            lesson_position=1, channel="telegram",
        )
    e.reversal["reversed"] = False
    e.invoices.credit(
        **scope, invoice_id=order.invoice_id, idempotency_key="credit-revoked",
    )
    assert not restored_access.require_access(**scope, program_id=p["id"], customer_id=cid)
    e.reversal["available"] = False
    with pytest.raises(RuntimeError, match="commercial_reversal_authority_unavailable"):
        e.paid_access.require_access(**scope, program_id=p["id"], customer_id=cid)


def test_manual_paid_and_mixed_partial_money_do_not_launder_as_verified_psp():
    e = environment()
    scope, order = e.scope, e.order
    e.invoices.record_payment(
        **scope, invoice_id=order.invoice_id, idempotency_key="manual-money",
        amount_minor=order.amount_minor,
    )
    assert e.paid_access.require_access(
        **scope, program_id=e.program["id"], customer_id=e.customer.customer_id,
    ) is False
    with pytest.raises(RuntimeError, match="commercial_settlement_paid_without_matching_proof"):
        e.settlement.reconcile(**scope, order_id=order.order_id)

    f = environment()
    f.invoices.record_payment(
        **f.scope, invoice_id=f.order.invoice_id,
        idempotency_key="partially-paid-manual", amount_minor=100,
    )
    with pytest.raises(RuntimeError, match="commercial_settlement_mixed_invoice_payments_not_supported"):
        f.settlement.reconcile(**f.scope, order_id=f.order.order_id)
    assert not f.paid_access.require_access(
        **f.scope, program_id=f.program["id"], customer_id=f.customer.customer_id,
    )


def test_wrong_psp_proof_cross_business_and_missing_reversal_are_fail_closed():
    e = environment()
    assert e.paid_access.require_access(
        tenant_id="tenant-a", business_id="business-b",
        program_id=e.program["id"], customer_id=e.customer.customer_id,
    ) is False
    e.verifier.evidence = replace(e.verifier.evidence, merchant_id="wrong-merchant")
    with pytest.raises(RuntimeError, match="commercial_settlement_provider_provenance_invalid"):
        e.settlement.reconcile(**e.scope, order_id=e.order.order_id)
    assert not e.paid_access.require_access(
        **e.scope, program_id=e.program["id"], customer_id=e.customer.customer_id,
    )
    with pytest.raises(TypeError, match="commercial_reversal_authority_required"):
        CanonicalPaidProgramAccess(
            purchases=e.purchases, checkouts=e.checkout, reversal_reader=None,
        )


def test_authenticated_settlement_route_denies_forged_money_and_reads_canonical_status(tmp_path):
    e = environment()
    keys = PersistentApiKeyStore(path=tmp_path / "keys.json", pepper="commercial-phase18")
    policy = ApiKeyPolicy(store=keys)
    _, owner = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="owner-a",
    )
    _, alien = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-b", subject="owner-b",
    )
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "security-audit.jsonl",
        ).api_surface_guard,
    )
    router = APIRouter()
    register_business_workspace_commercial_routes(
        router=router, auth_bundle=auth, purchases=e.purchases,
        checkout=e.checkout, settlement=e.settlement,
    )
    app = FastAPI()
    app.include_router(router)
    base = "/business-workspace/commercial/orders/" + e.order.order_id
    with TestClient(app, base_url="https://testserver") as client:
        headers = {"X-API-Key": owner}
        assert client.post(base + "/reconcile").status_code == 401
        assert client.post(base + "/reconcile", headers={"X-API-Key": alien}).status_code == 404
        assert client.post(base + "/reconcile", headers=headers, json={
            "status": "succeeded", "amount_minor": e.order.amount_minor,
        }).status_code == 422
        before = client.get(base, headers=headers)
        assert before.status_code == 200
        assert before.json()["provider_verified"] is False
        receipt = client.post(base + "/reconcile", headers=headers, json={})
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["provider_verified"] is True
        after = client.get(base, headers=headers)
        assert after.json()["provider_verified"] is True
        assert after.json()["paid_minor"] == e.order.amount_minor
        assert client.post(base + "/reconcile", headers=headers, json={}).json() == receipt.json()
        assert client.get(base, headers={"X-API-Key": alien}).status_code == 404
