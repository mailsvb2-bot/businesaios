"""Phase18 program enrollment: canonical BusinessFact, real API auth, bounded scope.

The minimal stub covers only the separate canonical Customer owner response; the
production route passes the actual CustomerRegistry and its PII vault.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_program_routes import register_business_workspace_program_routes
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from contracts.customer import CustomerNotFound, CustomerStatus
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class CanonicalCustomerBoundary:
    def __init__(self, eligible):
        self.eligible = eligible

    def get_customer(self, *, tenant_id, business_id, customer_id):
        if (tenant_id, business_id, customer_id) not in self.eligible:
            raise CustomerNotFound("not found in business")
        return SimpleNamespace(customer=SimpleNamespace(status=CustomerStatus.ACTIVE))


def test_owner_enrolls_existing_customer_without_fake_delivery_or_cross_business_leakage(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "auth.json", pepper="enrollment-pepper")
    policy = ApiKeyPolicy(store=keys)
    _, owner_key = policy.issue_owner_session(tenant_id="tenant", business_id="b1", subject="owner")
    _, other_key = policy.issue_owner_session(tenant_id="tenant", business_id="b2", subject="other")
    _, support_key = keys.issue(
        tenant_id="tenant", subject="support", roles=(RoleId.SUPPORT,), scopes=("support_case_manage",),
        ttl_seconds=3600, metadata={"business_id": "b1", "principal_kind": "user"},
    )
    customer_id = str(uuid4())
    unknown_id = str(uuid4())
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CanonicalCustomerBoundary({("tenant", "b1", customer_id)})
    registry = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    router = APIRouter()
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=policy),
        security_guard=ApiSecurityOwnerBundle.default(audit_path=tmp_path / "audit.jsonl").api_surface_guard,
    )
    register_business_workspace_program_routes(router=router, auth_bundle=auth, programs=registry)
    app = FastAPI()
    app.include_router(router)
    h1, h2, hs = ({"X-API-Key": key} for key in (owner_key, other_key, support_key))
    with TestClient(app, base_url="https://testserver") as client:
        publish = client.post("/business-workspace/programs", headers=h1, json={
            "title": "Two lessons", "idempotency_key": "p1",
            "lessons": [
                {"title": "Intro", "content_kind": "link", "content_ref": "https://example.org/a"},
                {"title": "Practice", "content_kind": "task", "content_ref": "asset:2"},
            ],
        })
        assert publish.status_code == 200, publish.text
        program = publish.json()
        path = "/business-workspace/programs/" + program["id"] + "/enrollments"
        assert client.post(path, json={"customer_id": customer_id}).status_code == 401
        assert client.post(path, headers=hs, json={"customer_id": customer_id}).status_code == 403
        assert client.post(path, headers=h2, json={"customer_id": customer_id}).status_code == 404
        assert client.get(path, headers=h2).status_code == 404
        assert client.post(path, headers=h1, json={"customer_id": unknown_id}).status_code == 404
        assert client.post(path, headers=h1, json={"customer_id": "not-a-uuid"}).status_code == 422
        assert client.post(path, headers=h1, json={"customer_id": customer_id, "admin": True}).status_code == 422
        assert len(events) == 1
        first = client.post(path, headers=h1, json={"customer_id": customer_id})
        assert first.status_code == 200, first.text
        receipt = first.json()
        assert receipt["customer_id"] == customer_id
        assert receipt["status"] == "awaiting_delivery"
        assert [x["status"] for x in receipt["progress"]] == ["pending", "pending"]
        assert len(events) == 2
        again = client.post(path, headers=h1, json={"customer_id": customer_id})
        assert again.status_code == 200 and again.json() == receipt
        assert len(events) == 2
        listing = client.get(path, headers=h1)
        assert listing.status_code == 200 and listing.json() == {"enrollments": [receipt]}
        # A restart replays exactly one enrollment from the shared Event Store.
        rebuilt = ProgramPublicationRegistry(
            event_store=events, idempotency_store=claims, customer_registry=customers,
        )
        assert rebuilt.list_enrollments(
            tenant_id="tenant", business_id="b1", program_id=program["id"],
        ) == [receipt]
        assert len(events) == 2
