"""Real FastAPI HTTP + real API-key authentication + canonical EventStore journey.

No monkeypatched authorize_request, no synthetic role bypass: an OWNER creates
a support case; a separately issued SUPPORT key claims and resolves it; OWNER
sees each durable outcome; a different business cannot enumerate or mutate it.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_support_case_routes import (
    register_business_workspace_support_case_routes,
)
from application.business_autonomy.support_case_registry import SupportCaseRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from scripts.support.issue_case_operator_access import issue_operator_access


class _AllowAuthenticationPerimeter:
    """Only the external transport/perimeter guard is substituted in this
    in-process HTTP test; API-key validity/roles/scope are completely real.
    """

    def enforce(self, **kwargs):
        return None


def test_owner_to_scoped_operator_to_owner_with_revocation_and_denial(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "canonical_auth.json", pepper="test-pepper")
    auth_policy = ApiKeyPolicy(store=keys)
    _, owner_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="real-owner"
    )
    support_id, support_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-a", operator_id="operator-one"
    )
    _, wrong_business_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-b", operator_id="operator-two"
    )
    event_store = MemoryEventStore()
    cases = SupportCaseRegistry(event_store=event_store, idempotency_store=InMemoryIdempotencyStore())
    router = APIRouter()
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=auth_policy),
        security_guard=_AllowAuthenticationPerimeter(),
    )
    register_business_workspace_support_case_routes(
        router=router, auth_bundle=auth, support_cases=cases
    )
    app = FastAPI()
    app.include_router(router)
    owner_headers = {"X-API-Key": owner_key}
    support_headers = {"X-API-Key": support_key}
    wrong_headers = {"X-API-Key": wrong_business_key}
    with TestClient(app) as client:
        owner_denied = client.get("/platform-support/session", headers=owner_headers)
        assert owner_denied.status_code == 403
        assert client.get("/platform-support/session").status_code == 401
        bound = client.get("/platform-support/session", headers=support_headers)
        assert bound.status_code == 200
        assert bound.json() == {
            "tenant_id": "tenant-a", "business_id": "business-a",
            "operator_id": "operator-one", "can_manage_cases": True,
        }
        assert support_key not in bound.text
        assert client.get("/business-workspace/support-cases", headers=support_headers).status_code == 403

        create = {"category": "technical", "summary": "Operator cannot access queue", "idempotency_key": "owner-submit"}
        created_response = client.post("/business-workspace/support-cases", headers=owner_headers, json=create)
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        assert created["status"] == "open" and created["revision"] == 1
        replay = client.post("/business-workspace/support-cases", headers=owner_headers, json=create)
        assert replay.status_code == 200 and replay.json()["id"] == created["id"]
        assert len(event_store) == 1

        queue = client.get("/platform-support/cases", headers=support_headers)
        assert queue.status_code == 200 and queue.json()["cases"] == [created]
        wrong_queue = client.get("/platform-support/cases", headers=wrong_headers)
        assert wrong_queue.status_code == 200 and wrong_queue.json()["cases"] == []
        assert client.post(
            "/platform-support/cases/" + created["id"] + "/claim",
            headers=wrong_headers, json={"expected_revision": 1, "idempotency_key": "stolen-claim"}
        ).status_code == 404

        action_url = "/platform-support/cases/" + created["id"]
        claim_body = {"expected_revision": 1, "idempotency_key": "operator-claim"}
        claimed_response = client.post(action_url + "/claim", headers=support_headers, json=claim_body)
        assert claimed_response.status_code == 200, claimed_response.text
        claimed = claimed_response.json()
        assert claimed["status"] == "claimed" and claimed["revision"] == 2
        assert client.get("/business-workspace/support-cases", headers=owner_headers).json()["cases"] == [claimed]
        claim_again = client.post(action_url + "/claim", headers=support_headers, json=claim_body)
        assert claim_again.status_code == 200 and claim_again.json()["id"] == created["id"]
        assert len(event_store) == 2

        stale = client.post(
            action_url + "/resolve", headers=support_headers,
            json={"expected_revision": 1, "idempotency_key": "stale-revision"}
        )
        assert stale.status_code == 409
        resolved_response = client.post(
            action_url + "/resolve", headers=support_headers,
            json={"expected_revision": 2, "idempotency_key": "operator-resolve"}
        )
        assert resolved_response.status_code == 200, resolved_response.text
        resolved = resolved_response.json()
        assert resolved["status"] == "resolved" and resolved["revision"] == 3
        assert client.get("/business-workspace/support-cases", headers=owner_headers).json()["cases"] == [resolved]
        assert len(event_store) == 3

        keys.revoke(support_id)
        assert client.get("/platform-support/cases", headers=support_headers).status_code == 401
        assert client.get("/business-workspace/support-cases", headers=owner_headers).status_code == 200
