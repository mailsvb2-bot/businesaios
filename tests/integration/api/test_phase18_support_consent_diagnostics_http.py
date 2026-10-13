"""Production-like real HTTP support consent from owner through operator to audit.

No mock authentication, second database or direct access to raw logs.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_support_case_routes import register_business_workspace_support_case_routes
from application.business_autonomy.support_case_registry import SupportCaseRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from scripts.support.issue_case_operator_access import issue_operator_access


def test_consent_claim_operator_diagnostics_audit_and_revocation_on_real_http(tmp_path):
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    keys = PersistentApiKeyStore(path=tmp_path / "canonical_keys.json", pepper="consent-test-pepper")
    policy = ApiKeyPolicy(store=keys)
    _, owner_key = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="owner-a",
    )
    _, wrong_owner_key = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-b", subject="owner-b",
    )
    _, support_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-a",
        operator_id="operator-a",
    )
    _, second_operator_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-a",
        operator_id="operator-b",
    )
    _, wrong_operator_key = issue_operator_access(
        store=keys, tenant_id="tenant-a", business_id="business-b",
        operator_id="operator-c",
    )
    cases = SupportCaseRegistry(event_store=events, idempotency_store=claims)
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "security_log.jsonl",
        ).api_surface_guard,
    )
    router = APIRouter()
    register_business_workspace_support_case_routes(
        router=router, auth_bundle=auth, support_cases=cases,
    )
    app = FastAPI()
    app.include_router(router)
    owner = {"X-API-Key": owner_key}
    support = {"X-API-Key": support_key}
    wrong_owner = {"X-API-Key": wrong_owner_key}
    alien = {"X-API-Key": wrong_operator_key}
    other_operator = {"X-API-Key": second_operator_key}
    with TestClient(app, base_url="https://testserver") as client:
        created = client.post(
            "/business-workspace/support-cases", headers=owner,
            json={"category": "technical", "summary": "Delivery lacks receipts",
                  "idempotency_key": "issue-one"},
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["id"]
        owner_access = "/business-workspace/support-cases/" + case_id
        operator_access = "/platform-support/cases/" + case_id
        assert client.post(operator_access + "/diagnostics", headers=support,
                           json={"idempotency_key": "early"}).status_code == 409
        assert client.post(owner_access + "/grant-access", headers=owner,
            json={"expected_case_revision": 1, "duration_seconds": 300,
                  "idempotency_key": "wrong-state"}).status_code == 409
        assert client.post(owner_access + "/grant-access", headers=support,
            json={"expected_case_revision": 1, "duration_seconds": 300,
                  "idempotency_key": "not-owner"}).status_code == 403

        claim = client.post(operator_access + "/claim", headers=support,
            json={"expected_revision": 1, "idempotency_key": "claim"})
        assert claim.status_code == 200, claim.text
        assert claim.json()["revision"] == 2
        assert client.get(operator_access + "/access", headers=other_operator).status_code == 403
        assert client.post(operator_access + "/diagnostics", headers=other_operator,
            json={"idempotency_key": "not-assigned"}).status_code == 409
        assert client.get(owner_access + "/access", headers=wrong_owner).status_code == 404
        assert client.post(operator_access + "/diagnostics", headers=alien,
            json={"idempotency_key": "foreign"}).status_code == 404
        assert client.get(operator_access + "/access", headers=owner).status_code == 403
        assert client.get("/control-plane/audit", headers=support).status_code in (403, 404)

        grant_body = {"expected_case_revision": 2, "duration_seconds": 300,
                      "idempotency_key": "owner-consent"}
        grant = client.post(owner_access + "/grant-access", headers=owner, json=grant_body)
        assert grant.status_code == 200, grant.text
        assert grant.json()["active"] is True
        grant_id = grant.json()["grant_id"]
        assert client.post(owner_access + "/grant-access", headers=owner, json=grant_body).json()["grant_id"] == grant_id
        assert client.post(owner_access + "/grant-access", headers=wrong_owner, json=grant_body).status_code == 404
        assert client.get(operator_access + "/access", headers=support).json()["active"] is True
        assert client.post(operator_access + "/diagnostics", headers=support,
            json={"idempotency_key": "trace", "user_data": "forbidden"}).status_code == 422

        receipt = client.post(operator_access + "/diagnostics", headers=support,
            json={"idempotency_key": "trace"})
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["grant_id"] == grant_id
        assert set(receipt.json()["counts"]) == {"messages", "payments", "programs", "support"}
        assert receipt.json()["window_hours"] == 24
        assert client.post(operator_access + "/diagnostics", headers=support,
            json={"idempotency_key": "trace"}).json() == receipt.json()
        audit = client.get(owner_access + "/access", headers=owner)
        assert audit.status_code == 200 and audit.json()["total"] == 2
        assert [x["action"] for x in audit.json()["entries"]] == ["granted", "diagnostics_viewed"]
        assert owner_key not in audit.text and support_key not in audit.text
        assert "operator-a" not in audit.text and "Delivery lacks receipts" not in audit.text

        # Reconstituted case owner sees exactly same durable facts, no local grants.
        restored = SupportCaseRegistry(event_store=events, idempotency_store=claims)
        restored_router = APIRouter()
        register_business_workspace_support_case_routes(
            router=restored_router, auth_bundle=auth, support_cases=restored,
        )
        restored_app = FastAPI()
        restored_app.include_router(restored_router)
        with TestClient(restored_app, base_url="https://testserver") as fresh:
            assert fresh.get(owner_access + "/access", headers=owner).json()["total"] == 2

        revoke_body = {"grant_id": grant_id, "idempotency_key": "withdraw-consent"}
        revoke = client.post(owner_access + "/revoke-access", headers=owner, json=revoke_body)
        assert revoke.status_code == 200 and revoke.json()["reason"] == "revoked"
        assert client.post(owner_access + "/revoke-access", headers=owner,
                           json=revoke_body).json() == revoke.json()
        assert client.post(operator_access + "/diagnostics", headers=support,
                           json={"idempotency_key": "after-withdraw"}).status_code == 409
        assert client.get(owner_access + "/access", headers=owner).json()["total"] == 3

        # New consent is possible only while the same operator still owns the case.
        second_grant = client.post(owner_access + "/grant-access", headers=owner,
            json={**grant_body, "idempotency_key": "new-consent"})
        assert second_grant.status_code == 200 and second_grant.json()["active"] is True
        resolve = client.post(operator_access + "/resolve", headers=support,
            json={"expected_revision": 2, "idempotency_key": "close"})
        assert resolve.status_code == 200 and resolve.json()["status"] == "resolved"
        assert client.get(owner_access + "/access", headers=owner).json()["reason"] == "case_changed"
        assert client.post(operator_access + "/diagnostics", headers=support,
                           json={"idempotency_key": "after-close"}).status_code == 409
        # Existing case lifecycle is untouched by the additional access events.
        trail = client.get(owner_access + "/history", headers=owner)
        assert trail.status_code == 200
        assert [x["action"] for x in trail.json()["entries"]] == [
            "created", "claimed", "resolved",
        ]
