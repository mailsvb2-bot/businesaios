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
