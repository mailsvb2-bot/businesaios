"""Owner create -> durable draft -> revise -> publish/archive with real HTTP and scope.

An event-sourced draft must remain accessible after a fresh registry instance
and may never be edited after publication or observed from another business.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_program_routes import register_business_workspace_program_routes
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_program_draft_can_be_resumed_revised_published_and_never_leaks_across_businesses(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "keys.json", pepper="draft-pepper")
    auth_policy = ApiKeyPolicy(store=keys)
    _, owner_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="owner-a",
    )
    _, other_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-b", subject="owner-b",
    )
    _, support_key = keys.issue(
        tenant_id="tenant-a", subject="support", roles=(RoleId.SUPPORT,),
        scopes=("support_case_manage",), ttl_seconds=3600,
        metadata={"business_id": "business-a", "principal_kind": "user"},
    )
    events, idempotency = MemoryEventStore(), InMemoryIdempotencyStore()
    registry = ProgramPublicationRegistry(event_store=events, idempotency_store=idempotency)
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=auth_policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "security-audit.jsonl",
        ).api_surface_guard,
    )
    router = APIRouter()
    register_business_workspace_program_routes(router=router, auth_bundle=auth, programs=registry)
    app = FastAPI()
    app.include_router(router)
    base = "/business-workspace/program-drafts"
    owner, other, support = ({"X-API-Key": key} for key in (owner_key, other_key, support_key))
    content = {
        "title": "A course to finish next week",
        "lessons": [{"title": "First", "content_kind": "link",
                     "content_ref": "https://example.org/first"}],
        "idempotency_key": "create-1",
    }
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(base).status_code == 401
        assert client.post(base, json=content, headers=support).status_code == 403
        assert client.get(base, headers=other).json() == {"drafts": []}
        result = client.post(base, json=content, headers=owner)
        assert result.status_code == 200, result.text
        draft = result.json()
        draft_url = base + "/" + draft["id"]
        assert draft["status"] == "draft" and draft["revision"] == 1
        assert len(draft["lessons"]) == 1 and len(events) == 1
        assert client.get(base, headers=owner).json()["drafts"] == [draft]
        assert client.get("/business-workspace/programs", headers=owner).json()["programs"] == []
        assert client.get("/business-workspace/programs/" + draft["id"], headers=other).status_code == 404
        assert client.post(draft_url, headers=other, json={
            "action": "publish", "expected_revision": 1, "idempotency_key": "stolen"
        }).status_code == 404

        # A crash after the server wrote the create fact must not duplicate it,
        # even after a save has changed the draft.
        assert client.post(base, json=content, headers=owner).json() == draft
        assert len(events) == 1
        saved_lessons = [
            *content["lessons"],
            {"title": "Second", "content_kind": "task", "content_ref": "asset:lesson-2"},
        ]
        save = {
            "action": "save", "expected_revision": 1, "idempotency_key": "save-2",
            "title": "Revised title", "lessons": saved_lessons,
        }
        updated = client.post(draft_url, headers=owner, json=save)
        assert updated.status_code == 200, updated.text
        revised = updated.json()
        assert revised["status"] == "draft" and revised["revision"] == 2
        assert revised["title"] == "Revised title" and len(revised["lessons"]) == 2
        assert len(events) == 2
        assert client.post(draft_url, headers=owner, json=save).json() == revised
        assert len(events) == 2

        # Retried creation refers to the original draft even after content was
        # edited. Different payload with the same create key must be rejected.
        assert client.post(base, json=content, headers=owner).json() == revised
        assert client.post(base, json=dict(content, title="Different"), headers=owner).status_code == 409
        assert len(events) == 2

        # No stale publisher or update can overwrite a later revision.
        stale = client.post(draft_url, headers=owner, json={
            "action": "publish", "expected_revision": 1, "idempotency_key": "stale"
        })
        assert stale.status_code == 409
        assert len(events) == 2
        publish = {"action": "publish", "expected_revision": 2, "idempotency_key": "publish-3"}
        outcome = client.post(draft_url, headers=owner, json=publish)
        assert outcome.status_code == 200, outcome.text
        published = outcome.json()
        assert published["status"] == "active" and published["revision"] == 3
        assert [lesson["title"] for lesson in published["lessons"]] == ["First", "Second"]
        assert client.post(draft_url, headers=owner, json=publish).json() == published
        assert len(events) == 3
        assert client.get(base, headers=owner).json()["drafts"] == []
        assert client.get("/business-workspace/programs", headers=owner).json()["programs"] == [published]
        assert client.post(draft_url, headers=owner, json=dict(save, expected_revision=3, idempotency_key="edit-after-publish")).status_code == 409
        assert client.get("/business-workspace/programs", headers=other).json()["programs"] == []

        restored = ProgramPublicationRegistry(event_store=events, idempotency_store=idempotency)
        assert restored.get(tenant_id="tenant-a", business_id="business-a", program_id=draft["id"]) == published
        assert restored.list_for_business(tenant_id="tenant-a", business_id="business-a") == [published]
        assert len(events) == 3

        # A second draft may be intentionally removed before it is public.
        second = client.post(base, headers=owner, json={
            "title": "Abandoned", "lessons": [], "idempotency_key": "second"
        })
        assert second.status_code == 200, second.text
        second_id = second.json()["id"]
        assert client.post(base + "/" + second_id, headers=owner, json={
            "action": "publish", "expected_revision": 1, "idempotency_key": "empty"
        }).status_code == 422
        archive = client.post(base + "/" + second_id, headers=owner, json={
            "action": "archive", "expected_revision": 1, "idempotency_key": "archive"
        })
        assert archive.status_code == 200 and archive.json()["status"] == "archived"
        assert client.get(base, headers=owner).json()["drafts"] == []
        assert client.get("/business-workspace/programs", headers=owner).json()["programs"] == [published]
