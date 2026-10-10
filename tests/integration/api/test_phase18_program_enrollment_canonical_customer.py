"""Canonical Customer + encrypted PII vault -> program enrollment -> durable outcome.

Unlike the HTTP boundary test, this test invokes the actual canonical Customer
owner, not a stub. No provider delivery is claimed before proof exists.
"""
from __future__ import annotations

from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


def test_real_customer_registry_enrollment_persists_and_blocks_archived_or_cross_business():
    events, claims, vault = MemoryEventStore(), InMemoryIdempotencyStore(), InMemorySecretVault()
    customers = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=vault)
    identity = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="phase18-test-user",
    )
    cid = identity.customer.customer_id
    assert identity.customer.business_id == "business"
    programs = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    published = programs.publish(
        tenant_id="tenant", business_id="business", actor_id="owner",
        title="Course", lessons=[
            {"title": "Intro", "content_kind": "link", "content_ref": "https://example.org/1"},
        ], idempotency_key="program1",
    )
    before = len(events)
    enrolled = programs.enroll_customer(
        tenant_id="tenant", business_id="business", actor_id="owner",
        program_id=published["id"], customer_id=cid,
    )
    assert enrolled["status"] == "awaiting_delivery"
    assert enrolled["progress"] == [{"position": 1, "status": "pending"}]
    assert len(events) == before + 1
    assert programs.enroll_customer(
        tenant_id="tenant", business_id="business", actor_id="owner",
        program_id=published["id"], customer_id=cid,
    ) == enrolled
    assert len(events) == before + 1
    restarted = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    assert restarted.list_enrollments(
        tenant_id="tenant", business_id="business", program_id=published["id"],
    ) == [enrolled]
    try:
        restarted.enroll_customer(
            tenant_id="tenant", business_id="other", actor_id="owner",
            program_id=published["id"], customer_id=cid,
        )
    except KeyError:
        pass
    else:
        raise AssertionError("an enrollment leaked across businesses")
    customers.archive_customer(
        tenant_id="tenant", business_id="business", customer_id=cid,
    )
    try:
        restarted.enroll_customer(
            tenant_id="tenant", business_id="business", actor_id="owner",
            program_id=published["id"], customer_id=cid,
        )
    except RuntimeError as exc:
        assert str(exc) == "enrollment_customer_not_active"
    else:
        raise AssertionError("an archived customer was enrolled")

def test_lesson_send_plan_resolves_only_active_canonical_identity_and_does_not_send():
    events, claims, vault = MemoryEventStore(), InMemoryIdempotencyStore(), InMemorySecretVault()
    customers = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=vault)
    identity = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="12345678",
    )
    registry = ProgramPublicationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    program = registry.publish(tenant_id="tenant", business_id="business", actor_id="owner",
        title="Introduction", lessons=[{"title": "Part one", "content_kind": "link",
            "content_ref": "https://example.org/one"}], idempotency_key="one")
    enrolled = registry.enroll_customer(tenant_id="tenant", business_id="business", actor_id="owner",
        program_id=program["id"], customer_id=identity.customer.customer_id)
    size = len(events)
    plan = registry.lesson_send_plan(tenant_id="tenant", business_id="business",
        program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
        channel="telegram")
    assert plan["recipient"] == "12345678"
    assert plan["provider_key"] == "telegram_bot"
    assert plan["action_type"] == "send_message@v1"
    assert plan["text"] == "Программа: Introduction\nУрок 1: Part one\nhttps://example.org/one"
    assert plan["execution_allowed"] is False
    assert plan["status"] == "requires_owner_review_and_approval"
    assert len(events) == size  # no synthetic delivery event and no outbound write
    import pytest
    with pytest.raises(ValueError, match="program_delivery_channel_unsupported"):
        registry.lesson_send_plan(tenant_id="tenant", business_id="business",
            program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
            channel="unknown")
    with pytest.raises(KeyError, match="program_not_found"):
        registry.lesson_send_plan(tenant_id="tenant", business_id="other",
            program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
            channel="telegram")
    with pytest.raises(RuntimeError, match="program_delivery_identity_missing"):
        registry.lesson_send_plan(tenant_id="tenant", business_id="business",
            program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
            channel="email")
    customers.archive_customer(tenant_id="tenant", business_id="business",
        customer_id=identity.customer.customer_id)
    with pytest.raises(RuntimeError, match="enrollment_customer_not_active"):
        registry.lesson_send_plan(tenant_id="tenant", business_id="business",
            program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
            channel="telegram")

def test_provider_acceptance_is_durable_but_never_claims_recipient_delivery():
    from application.commerce.phase18_program_lesson_delivery import (
        reconcile_program_lesson_provider_acceptance,
    )
    from types import SimpleNamespace
    import pytest

    events, claims, vault = MemoryEventStore(), InMemoryIdempotencyStore(), InMemorySecretVault()
    customers = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=vault)
    identity = customers.ensure_customer_identity(
        tenant_id="t", business_id="b", channel="telegram", external_subject="44444",
    )
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    program = programs.publish(tenant_id="t", business_id="b", actor_id="owner", title="Course",
        lessons=[{"title": "Lesson", "content_kind": "link",
                  "content_ref": "https://example.org/lesson"}], idempotency_key="proof")
    enrolled = programs.enroll_customer(tenant_id="t", business_id="b", actor_id="owner",
        program_id=program["id"], customer_id=identity.customer.customer_id)
    plan = programs.lesson_send_plan(tenant_id="t", business_id="b",
        program_id=program["id"], enrollment_id=enrolled["id"], lesson_position=1,
        channel="telegram")
    fingerprint = "a" * 64
    approval = SimpleNamespace(
        status="approved",
        request=SimpleNamespace(tenant_id="t", subject_fingerprint="s" * 64, metadata={
            "action_name": "provider.telegram_bot.message_send",
            "decision_id": "decision1",
            "approval_request_fingerprint": fingerprint,
            "approval_resume_context": {
                "business_id": "b", "provider_key": "telegram_bot",
                "operation": "message_send",
                "payload": {"chat_id": plan["recipient"], "text": plan["text"]},
            },
        }),
    )
    decision = SimpleNamespace(
        decision_id="decision1", action="send_message@v1",
        payload={"business_id": "b", "provider_key": "telegram_bot",
                 "user_id": plan["recipient"], "text": plan["text"]},
    )
    job_id = "provider-sync-telegram_bot-" + ("s" * 32)
    rows = {}
    class FakeService:
        def find_provider_sync_history_jobs(self, *, tenant_id, business_id, provider_key, queue_job_ids):
            assert (tenant_id, business_id, provider_key) == ("t", "b", "telegram_bot")
            assert queue_job_ids == (job_id,)
            return dict(rows)
    class FakeAdmin:
        approval_store_factory = staticmethod(lambda: SimpleNamespace(
            get=lambda approval_id: approval if approval_id == "approval1" else None,
        ))
        decision_loader = staticmethod(lambda **kwargs: SimpleNamespace(decision=decision))
        _service = staticmethod(lambda business_id: FakeService())
    def reconcile(**overrides):
        return reconcile_program_lesson_provider_acceptance(
            programs=programs, provider_admin_handlers=FakeAdmin(),
            tenant_id="t", business_id="b", program_id=program["id"],
            enrollment_id=enrolled["id"], lesson_position=1,
            channel="telegram", approval_id="approval1", **overrides,
        )
    start = len(events)
    pending = reconcile()
    assert pending["status"] == "awaiting_provider_evidence"
    assert len(events) == start
    rows[job_id] = {
        "tenant_id": "t", "business_id": "b", "provider_key": "telegram_bot",
        "queue_job_id": job_id, "operation": "message_send", "mode": "live",
        "status": "live_executed", "accepted": True,
        "parsed_response": {"resource_id": "msg-real-1"},
        "history_id": "history-real-1",
        "recorded_at_utc": "2026-10-10T17:00:00+00:00",
    }
    accepted = reconcile()
    assert accepted["status"] == "provider_accepted"
    assert accepted["provider_accepted"] is True
    assert accepted["recipient_delivery_confirmed"] is False
    assert len(events) == start + 1
    assert reconcile()["outcome"] == accepted["outcome"]
    assert len(events) == start + 1
    outcomes = programs.list_lesson_provider_outcomes(
        tenant_id="t", business_id="b", program_id=program["id"],
        enrollment_id=enrolled["id"],
    )
    assert len(outcomes) == 1 and outcomes[0]["history_id"] == "history-real-1"
    with pytest.raises(KeyError):
        programs.list_lesson_provider_outcomes(
            tenant_id="t", business_id="other", program_id=program["id"],
            enrollment_id=enrolled["id"],
        )
    approval.request.metadata["approval_resume_context"]["payload"]["chat_id"] = "someone-else"
    with pytest.raises(ValueError, match="program_delivery_approval_content_mismatch"):
        reconcile()
    approval.request.metadata["approval_resume_context"]["payload"]["chat_id"] = plan["recipient"]
    rows[job_id]["accepted"] = False
    # Previously proven observation remains durable; a later forged failed
    # provider response cannot manufacture a second acceptance event.
    assert reconcile()["status"] == "provider_not_confirmed"
    assert len(events) == start + 1
