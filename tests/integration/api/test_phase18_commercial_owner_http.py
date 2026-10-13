"""Authenticated commercial owner HTTP: scopes, money truth, checkout fail-closed."""
from __future__ import annotations

from types import SimpleNamespace
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_commercial_routes import register_business_workspace_commercial_routes
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from contracts.customer import Customer, CustomerRecord
from core.offers.offer_types import OfferSummary
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class Customers:
    def get_customer(self, *, tenant_id, business_id, customer_id):
        if customer_id != "customer-a":
            raise LookupError("customer_not_found")
        return CustomerRecord(customer=Customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        ))


class Offers:
    def resolve(self, *, key):
        return SimpleNamespace(id="catalog@v1", list_offers=lambda: [OfferSummary(
            offer_id="approved", title="Real course", base_price_rub=500,
            meta={"program_id": key.product_id, "business_id": key.business_id},
        )])


def test_owner_scoped_order_payment_visibility_and_psp_guard(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "keys.json", pepper="commercial-test")
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
    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    leads.create(**scope, lead_id="lead-a", idempotency_key="lead-a",
                 customer_id="customer-a", conversation_id="conversation-a", channel="telegram")
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    published = programs.publish(
        access_mode="paid",
        **scope, actor_id="owner-a", title="Existing course", idempotency_key="course",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Text"}],
    )
    purchasing = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs, offers=Offers(),
        orders=OrderStore(event_store=events),
        invoices=InvoiceRegistry(event_store=events, idempotency_store=idem),
    )
    router = APIRouter()
    register_business_workspace_commercial_routes(router=router, auth_bundle=auth,
                                                   purchases=purchasing)
    app = FastAPI()
    app.include_router(router)
    base = "/business-workspace/commercial"
    body = {"lead_id": "lead-a", "customer_id": "customer-a",
            "program_id": published["id"], "offer_id": "approved",
            "idempotency_key": "buy-one"}
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post(base + "/orders", json=body).status_code == 401
        assert client.post(base + "/orders", headers={"X-API-Key": alien},
                           json=body).status_code == 404
        owner_headers = {"X-API-Key": owner}
        leads_response = client.get(base + "/leads", headers=owner_headers)
        assert leads_response.status_code == 200
        assert leads_response.json()["leads"][0]["customer_id"] == "customer-a"
        assert client.get(base + "/leads", headers={"X-API-Key": alien}).json() == {"leads": []}
        quote = client.get(base + "/offers/" + published["id"], headers=owner_headers)
        assert quote.status_code == 200 and quote.json()["offers"][0]["amount_minor"] == 50000
        made = client.post(base + "/orders", headers=owner_headers, json=body)
        assert made.status_code == 200, made.text
        order = made.json()
        assert order["amount_minor"] == 50000 and order["invoice_status"] == "issued"
        assert client.post(base + "/orders", headers=owner_headers, json=body).json() == order
        detail = client.get(base + "/orders/" + order["order_id"], headers=owner_headers)
        assert detail.status_code == 200
        assert detail.json()["invoice_status"] == "issued"
        assert detail.json()["provider_verified"] is False
        assert client.get(base + "/orders/" + order["order_id"],
                          headers={"X-API-Key": alien}).status_code == 404
        assert client.get(base + "/orders", headers={"X-API-Key": alien}).json() == {"orders": []}
        assert len(client.get(base + "/orders", headers=owner_headers).json()["orders"]) == 1
        denied = client.post(base + "/orders/" + order["order_id"] + "/checkout",
                             headers=owner_headers)
        assert denied.status_code == 503
        assert denied.json()["detail"] == "commercial_psp_unconfigured"
        assert client.post(base + "/orders", headers=owner_headers,
                           json={**body, "amount_minor": 1}).status_code == 422
