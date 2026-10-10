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
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from scripts.support.issue_case_operator_access import issue_operator_access



def test_owner_to_scoped_operator_to_owner_with_revocation_and_denial(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "canonical_auth.json", pepper="test-pepper")
    auth_policy = ApiKeyPolicy(store=keys)
    _, owner_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="real-owner"
    )
    support_id, support_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-a", operator_id="operator-one"
    )
    _, unscoped_support_key = keys.issue(
        tenant_id="tenant-a", subject="unscoped-support",
        roles=(RoleId.SUPPORT,), scopes=(),
        metadata={"principal_kind": "user", "business_id": "business-a"},
        ttl_seconds=3600,
    )
    _, wrong_business_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-b", operator_id="operator-two"
    )
    event_store = MemoryEventStore()
    cases = SupportCaseRegistry(event_store=event_store, idempotency_store=InMemoryIdempotencyStore())
    router = APIRouter()
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=auth_policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "canonical_security_audit.jsonl"
        ).api_surface_guard,
    )
    register_business_workspace_support_case_routes(
        router=router, auth_bundle=auth, support_cases=cases
    )
    app = FastAPI()
    app.include_router(router)
    owner_headers = {"X-API-Key": owner_key}
    support_headers = {"X-API-Key": support_key}
    wrong_headers = {"X-API-Key": wrong_business_key}
    with TestClient(app, base_url="https://testserver") as client:
        owner_denied = client.get("/platform-support/session", headers=owner_headers)
        assert owner_denied.status_code == 403
        assert client.get("/platform-support/session").status_code == 401
        assert client.get("/platform-support/session", headers={"X-API-Key": unscoped_support_key}).status_code == 403
        bound = client.get("/platform-support/session", headers=support_headers)
        assert bound.status_code == 200, bound.text
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
        # The same resolve request still acknowledges its exact durable result.
        resolve_replay = client.post(
            action_url + "/resolve", headers=support_headers,
            json={"expected_revision": 2, "idempotency_key": "operator-resolve"},
        )
        assert resolve_replay.status_code == 200 and resolve_replay.json() == resolved
        # Old claim may never report today's resolved state as claim success.
        stale_claim = client.post(action_url + "/claim", headers=support_headers, json=claim_body)
        assert stale_claim.status_code == 409
        assert stale_claim.json()["detail"] == "support_case_replay_stale"
        assert client.get("/business-workspace/support-cases", headers=owner_headers).json()["cases"] == [resolved]
        # Operator queue is actionable work only; resolved cases remain in
        # durable owner history, not the pending-work queue.
        after_resolve_queue = client.get("/platform-support/cases", headers=support_headers)
        assert after_resolve_queue.status_code == 200
        assert after_resolve_queue.json()["cases"] == []
        assert len(event_store) == 3

        # A resolved case is absent from the actionable operator queue, but
        # its audit history remains available by exact ID to the same
        # scoped support operator, never to another business.
        assert client.get("/platform-support/cases", headers=support_headers).json()["cases"] == []
        operator_detail_url = "/platform-support/cases/" + created["id"]
        detail = client.get(operator_detail_url, headers=support_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json() == resolved
        assert detail.json()["summary"] == created["summary"]
        assert client.get(operator_detail_url, headers=wrong_headers).status_code == 404
        assert client.get(operator_detail_url, headers=owner_headers).status_code == 403
        # GET /{case_id}/raw-audit matches the registered POST action
        # pattern, so FastAPI returns 405 without dispatching the request.
        # The canonical security policy independently denies that path.
        denied_audit = client.get(operator_detail_url + "/raw-audit", headers=support_headers)
        assert denied_audit.status_code == 405
        assert denied_audit.json()["detail"] == "Method Not Allowed"
        assert created["summary"] not in denied_audit.text

        operator_history_url = "/platform-support/cases/" + created["id"] + "/history"
        operator_history = client.get(operator_history_url, headers=support_headers)
        assert operator_history.status_code == 200, operator_history.text
        assert [entry["action"] for entry in operator_history.json()["entries"]] == [
            "created", "claimed", "resolved",
        ]
        assert client.get(operator_history_url, headers=wrong_headers).status_code == 404
        assert client.get(operator_history_url, headers=owner_headers).status_code == 403

        history_url = "/business-workspace/support-cases/" + created["id"] + "/history"
        history_response = client.get(history_url, headers=owner_headers)
        assert history_response.status_code == 200, history_response.text
        trail = history_response.json()
        assert trail["case_id"] == created["id"] and trail["revision"] == 3
        assert trail["total"] == 3 and not trail["truncated"]
        assert [entry["action"] for entry in trail["entries"]] == ["created", "claimed", "resolved"]
        assert all(entry["occurred_at"] for entry in trail["entries"])
        assert "operator-one" not in history_response.text
        assert "operator-resolve" not in history_response.text
        assert client.get(history_url, headers=support_headers).status_code == 403
        _, other_owner_key = auth_policy.issue_owner_session(
            tenant_id="tenant-a", business_id="business-b", subject="other-owner"
        )
        assert client.get(history_url, headers={"X-API-Key": other_owner_key}).status_code == 404
        assert client.get(history_url + "?limit=0", headers=owner_headers).status_code == 422

        keys.revoke(support_id)
        assert client.get("/platform-support/cases", headers=support_headers).status_code == 401
        assert client.get(operator_history_url, headers=support_headers).status_code == 401
        assert client.get(operator_detail_url, headers=support_headers).status_code == 401
        assert client.get("/business-workspace/support-cases", headers=owner_headers).status_code == 200
