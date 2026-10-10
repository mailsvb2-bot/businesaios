"""Phase 18: authenticated HTTP publication -> real customer -> approval -> provider proof.

Provider and approval observations are controlled test fixtures. This exercises
real FastAPI auth, owner role, real CRM and Event Spine, not a live provider.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.business_workspace_program_routes import register_business_workspace_program_routes
from adapters.api.fastapi.business_workspace_provider_routes import register_business_workspace_provider_routes
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from crm.customer_registry import CustomerRegistry
from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


def test_real_owner_http_program_to_provider_acceptance_is_durable_and_isolated(tmp_path):
    event_store, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=event_store, idempotency_store=claims,
        pii_vault=InMemorySecretVault(),
    )
    identity = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="123456789",
    )
    programs = ProgramPublicationRegistry(
        event_store=event_store, idempotency_store=claims,
        customer_registry=customers,
    )
    keys = PersistentApiKeyStore(path=tmp_path / "keys.json", pepper="phase18-delivery-pepper")
    policy = ApiKeyPolicy(store=keys)
    _, owner_key = policy.issue_owner_session(
        tenant_id="tenant", business_id="business", subject="owner",
    )
    _, stranger_key = policy.issue_owner_session(
        tenant_id="tenant", business_id="stranger", subject="stranger",
    )
    _, support_key = keys.issue(
        tenant_id="tenant", subject="support", roles=(RoleId.SUPPORT,),
        scopes=("support_case_manage",), ttl_seconds=3600,
        metadata={"business_id": "business", "principal_kind": "user"},
    )
    approval_id, decision_id = "approval-phase18-one", "decision-phase18-one"
    fingerprint = "d" * 64
    subject_fingerprint = "e" * 64
    approval = None
    decision = None
    history = {}
    class FakeProviderService:
        def find_provider_sync_history_jobs(self, *, tenant_id, business_id, provider_key, queue_job_ids):
            assert (tenant_id, business_id, provider_key) == ("tenant", "business", "telegram_bot")
            return {key: history[key] for key in queue_job_ids if key in history}

    class FakeProviderAdmin:
        approval_store_factory = staticmethod(lambda: SimpleNamespace(
            get=lambda key: approval if key == approval_id else None,
        ))
        decision_loader = staticmethod(lambda **kwargs: SimpleNamespace(decision=decision))
        _service = staticmethod(lambda business_id: FakeProviderService())

    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "audit.jsonl",
        ).api_surface_guard,
    )
    router = APIRouter()
    register_business_workspace_program_routes(
        router=router, auth_bundle=auth, programs=programs,
        provider_admin_handlers=FakeProviderAdmin(),
    )
    # The actual owner-facing customer endpoint must see the exact same
    # registry and event chronology as program enrollment, not a shadow CRM.
    register_business_workspace_provider_routes(
        router=router, auth_bundle=auth,
        provider_admin_handlers=ProviderAdminRouteHandlers(
            customer_event_store=event_store, customer_registry=customers,
        ),
    )
    app = FastAPI()
    app.include_router(router)
    owner = {"X-API-Key": owner_key}
    stranger = {"X-API-Key": stranger_key}
    support = {"X-API-Key": support_key}
    with TestClient(app, base_url="https://testserver") as client:
        roster = client.get("/business-workspace/customers", headers=owner)
        assert roster.status_code == 200, roster.text
        assert roster.json()["customers"][0]["customer_id"] == identity.customer.customer_id
        assert roster.json()["customers"][0]["identities"][0]["external_subject"] == "123456789"
        assert client.get("/business-workspace/customers", headers=stranger).json()["customers"] == []
        assert client.get("/business-workspace/customers", headers=support).status_code == 403
        pub = client.post("/business-workspace/programs", headers=owner, json={
            "title": "Materials", "idempotency_key": "pub",
            "lessons": [{"title": "Intro", "content_kind": "link",
                         "content_ref": "https://example.org/material"}],
        })
        assert pub.status_code == 200, pub.text
        program = pub.json()
        base_path = "/business-workspace/programs/" + program["id"]
        enrolled = client.post(base_path + "/enrollments", headers=owner, json={
            "customer_id": identity.customer.customer_id,
        })
        assert enrolled.status_code == 200, enrolled.text
        enrollment = enrolled.json()
        customer_history = client.get(
            "/business-workspace/customers?customer_id=" + identity.customer.customer_id,
            headers=owner,
        )
        assert customer_history.status_code == 200
        assert any(
            row["kind"] == "program.enrollment_created"
            for row in customer_history.json()["timeline"]["entries"]
        )
        lesson_path = (
            base_path + "/enrollments/" + enrollment["id"] + "/lessons/1"
        )
        send_path = lesson_path + "/send-plan?channel=telegram"
        for headers, expected in (({}, 401), (support, 403), (stranger, 404)):
            assert client.get(send_path, headers=headers).status_code == expected
        plan_result = client.get(send_path, headers=owner)
        assert plan_result.status_code == 200, plan_result.text
        plan = plan_result.json()
        assert plan["recipient"] == "123456789"
        assert plan["execution_allowed"] is False
        assert plan["next_boundary"] == "/actions/execute"
        assert "https://example.org/material" in plan["text"]
        assert client.get(lesson_path + "/send-plan?channel=email", headers=owner).status_code == 409
        assert client.get(lesson_path + "/send-plan?channel=wrong", headers=owner).status_code == 422

        approval = SimpleNamespace(
            status="approved",
            request=SimpleNamespace(tenant_id="tenant", subject_fingerprint=subject_fingerprint, metadata={
                "action_name": "provider.telegram_bot.message_send",
                "decision_id": decision_id,
                "approval_request_fingerprint": fingerprint,
                "approval_resume_context": {
                    "business_id": "business", "provider_key": "telegram_bot",
                    "operation": "message_send",
                    "payload": {"chat_id": plan["recipient"], "text": plan["text"]},
                },
            }),
        )
        decision = SimpleNamespace(decision_id=decision_id, action="send_message@v1",
            payload={
                "business_id": "business", "provider_key": "telegram_bot",
                "user_id": plan["recipient"], "text": plan["text"],
            })
        rec_path = lesson_path + "/reconcile"
        outcomes_path = base_path + "/enrollments/" + enrollment["id"] + "/provider-outcomes"
        body = {"channel": "telegram", "approval_id": approval_id}
        before = len(event_store)
        for headers, status in (({}, 401), (support, 403), (stranger, 404)):
            assert client.post(rec_path, headers=headers, json=body).status_code == status
            assert client.get(outcomes_path, headers=headers).status_code == status
        assert client.post(rec_path, headers=owner, json={
            **body, "delivered": True,
        }).status_code == 422
        assert client.post(rec_path, headers=owner, json={
            "channel": "telegram", "approval_id": "not-owned",
        }).status_code == 404
        pending = client.post(rec_path, headers=owner, json=body)
        assert pending.status_code == 200 and pending.json()["status"] == "awaiting_provider_evidence"
        assert len(event_store) == before

        job_id = "provider-sync-telegram_bot-" + subject_fingerprint[:32]
        history[job_id] = {
            "tenant_id": "tenant", "business_id": "business",
            "provider_key": "telegram_bot", "queue_job_id": job_id,
            "operation": "message_send", "mode": "live",
            "status": "live_executed", "accepted": True,
            "parsed_response": {"resource_id": "provider-ack-1"},
            "history_id": "real-provider-evidence-1",
            "recorded_at_utc": "2026-10-10T16:10:00+00:00",
        }
        first = client.post(rec_path, headers=owner, json=body)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "provider_accepted"
        assert first.json()["recipient_delivery_confirmed"] is False
        assert first.json()["outcome"]["customer_id"] == identity.customer.customer_id
        assert len(event_store) == before + 1
        timeline_after = client.get(
            "/business-workspace/customers?customer_id=" + identity.customer.customer_id,
            headers=owner,
        )
        assert timeline_after.status_code == 200
        events = timeline_after.json()["timeline"]["entries"]
        provider_entries = [row for row in events if row["kind"] == "program.lesson_provider_accepted"]
        assert len(provider_entries) == 1
        assert provider_entries[0]["title"] == "Урок принят провайдером; доставка клиенту не подтверждена"
        again = client.post(rec_path, headers=owner, json=body)
        assert again.status_code == 200 and again.json() == first.json()
        assert len(event_store) == before + 1
        evidence = client.get(outcomes_path, headers=owner)
        assert evidence.status_code == 200
        assert evidence.json()["outcomes"] == [first.json()["outcome"]]
        restarted = ProgramPublicationRegistry(
            event_store=event_store, idempotency_store=claims,
            customer_registry=customers,
        )
        assert restarted.list_lesson_provider_outcomes(
            tenant_id="tenant", business_id="business",
            program_id=program["id"], enrollment_id=enrollment["id"],
        ) == evidence.json()["outcomes"]
        assert len(event_store) == before + 1
