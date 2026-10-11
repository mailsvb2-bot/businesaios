"""Phase-18 multi-lesson owner publication over real authentication + canonical EventStore."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_program_routes import (
    register_business_workspace_program_routes,
)
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _body():
    return {
        "title": "Introduction to the practice",
        "lessons": [
            {"title": "Getting started", "content_kind": "link", "content_ref": "https://example.org/lesson-1"},
            {"title": "First exercise", "content_kind": "task", "content_ref": "lesson-asset-002"},
            {"title": "Final review", "content_kind": "video", "content_ref": "lesson-asset-003"},
        ],
        "idempotency_key": "publish-first",
    }


def test_owner_publishes_complete_multi_lesson_program_without_parallel_store(tmp_path):
    keys = PersistentApiKeyStore(path=tmp_path / "keys.json", pepper="program-pepper")
    auth_policy = ApiKeyPolicy(store=keys)
    _, owner_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="owner-a",
    )
    _, other_key = auth_policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-b", subject="owner-b",
    )
    _, support_key = keys.issue(
        tenant_id="tenant-a", subject="operator", roles=(RoleId.SUPPORT,),
        scopes=("support_case_manage",), ttl_seconds=3600,
        metadata={"business_id": "business-a", "principal_kind": "user"},
    )
    events = MemoryEventStore()
    idempotency = InMemoryIdempotencyStore()
    programs = ProgramPublicationRegistry(
        event_store=events, idempotency_store=idempotency,
    )
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=auth_policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "security-audit.jsonl",
        ).api_surface_guard,
    )
    router = APIRouter()
    register_business_workspace_program_routes(
        router=router, auth_bundle=auth, programs=programs,
    )
    app = FastAPI()
    app.include_router(router)
    path = "/business-workspace/programs"
    owner = {"X-API-Key": owner_key}
    other = {"X-API-Key": other_key}
    support = {"X-API-Key": support_key}

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(path).status_code == 401
        assert client.post(path, headers=support, json=_body()).status_code == 403
        assert client.get(path, headers=support).status_code == 403
        assert client.get(path, headers=other).json() == {"programs": []}

        request = _body()
        first = client.post(path, headers=owner, json=request)
        assert first.status_code == 200, first.text
        published = first.json()
        assert published["status"] == "active"
        assert published["title"] == request["title"]
        assert len(published["lessons"]) == 3
        assert [lesson["position"] for lesson in published["lessons"]] == [1, 2, 3]
        assert len(events) == 1  # one all-or-nothing canonical BusinessFact

        replay = client.post(path, headers=owner, json=request)
        assert replay.status_code == 200, replay.text
        assert replay.json() == published and len(events) == 1

        item = client.get(path + "/" + published["id"], headers=owner)
        assert item.status_code == 200 and item.json() == published
        listing = client.get(path, headers=owner)
        assert listing.status_code == 200 and listing.json()["programs"] == [published]

        # A second instance projects the complete lesson list from the
        # original canonical store, not a private program database.
        restored = ProgramPublicationRegistry(event_store=events, idempotency_store=idempotency)
        assert restored.get(
            tenant_id="tenant-a", business_id="business-a",
            program_id=published["id"],
        ) == published

        assert client.get(path + "/" + published["id"], headers=other).status_code == 404
        assert client.get(path, headers=other).json()["programs"] == []
        assert client.post(path, headers=other, json=request).status_code == 200
        assert len(events) == 2
        assert client.get(path, headers=owner).json()["programs"] == [published]

        changed = dict(request, title="A different course")
        conflict = client.post(path, headers=owner, json=changed)
        assert conflict.status_code == 409
        assert conflict.json()["detail"] == "program_idempotency_conflict"
        assert len(events) == 2

        for invalid in (
            dict(request, lessons=[]),
            dict(request, lessons=request["lessons"] * 34),
            dict(request, lessons=[dict(request["lessons"][0], content_ref="http://insecure.example")]),
            dict(request, lessons=[dict(request["lessons"][0], content_kind="unknown")]),
            dict(request, idempotency_key="bad:password?"),
            dict(request, extra="caller-injected"),
        ):
            denied = client.post(path, headers=owner, json=invalid)
            assert denied.status_code == 422, denied.text
            assert len(events) == 2
        assert client.get(path + "?limit=0", headers=owner).status_code == 422
