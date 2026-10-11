"""Adversarial Phase-18 proof that one lesson cannot acquire two accepted receipts."""
from __future__ import annotations

import pytest

from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


def test_stale_competing_provider_acceptance_cannot_append_second_fact(monkeypatch):
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault(),
    )
    created = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="123456789",
    )
    first = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    program = first.publish(
        tenant_id="tenant", business_id="business", actor_id="owner",
        title="Programme", lessons=[{
            "title": "Lesson", "content_kind": "link",
            "content_ref": "https://example.org/lesson",
        }], idempotency_key="publish-once",
    )
    enrollment = first.enroll_customer(
        tenant_id="tenant", business_id="business", actor_id="owner",
        program_id=program["id"], customer_id=created.customer.customer_id,
    )
    scope = dict(
        tenant_id="tenant", business_id="business",
        program_id=program["id"], enrollment_id=enrollment["id"],
    )
    observed = first.record_provider_acceptance(
        **scope, lesson_position=1, provider_key="telegram_bot",
        approval_id="approved-a", decision_id="decision-a",
        provider_message_id="provider-message-a", history_id="history-a",
        recorded_at_ms=1234567890000,
    )
    assert observed["recipient_delivery_confirmed"] is False

    stale = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    # Simulate a real race: a second process read the projection *before*
    # the first committed, and therefore sees no prior provider acceptance.
    monkeypatch.setattr(stale, "list_lesson_provider_outcomes", lambda **_kwargs: [])
    with pytest.raises(RuntimeError, match="^program_lesson_already_provider_accepted$"):
        stale.record_provider_acceptance(
            **scope, lesson_position=1, provider_key="telegram_bot",
            approval_id="approved-b", decision_id="decision-b",
            provider_message_id="provider-message-b", history_id="history-b",
            recorded_at_ms=1234567890010,
        )
    assert first.list_lesson_provider_outcomes(**scope) == [observed]
    assert first.record_provider_acceptance(
        **scope, lesson_position=1, provider_key="telegram_bot",
        approval_id="approved-a", decision_id="decision-a",
        provider_message_id="provider-message-a", history_id="history-a",
        recorded_at_ms=1234567890000,
    ) == observed


def _stale_program_registry(monkeypatch, fresh, original):
    """Simulate an optimistic read completed before another writer committed."""
    real_get = fresh.get
    calls = 0

    def read_once_stale(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyError("simulated_pre_commit_snapshot")
        return real_get(**kwargs)

    monkeypatch.setattr(fresh, "get", read_once_stale)


def test_concurrent_same_key_publication_never_poisons_catalog(monkeypatch):
    from application.commerce import phase18_program_publication_registry as program_module

    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    first = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    payload = dict(
        tenant_id="tenant", business_id="business", actor_id="owner",
        title="Original", lessons=[{
            "title": "Lesson", "content_kind": "text", "content_ref": "Hello",
        }], idempotency_key="same-publish",
    )
    initial = first.publish(**payload)
    second = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    _stale_program_registry(monkeypatch, second, initial)
    before = len(events)
    # Guarantee the losing writer builds a different timestamped payload.
    with monkeypatch.context() as time_patch:
        time_patch.setattr(program_module.time, "time", lambda: 2000000000.5)
        with pytest.raises(RuntimeError, match="^program_creation_in_progress$"):
            second.publish(**payload)
    assert len(events) == before
    assert first.get(tenant_id="tenant", business_id="business", program_id=initial["id"]) == initial
    assert first.publish(**payload) == initial
    assert len(first.list_for_business(tenant_id="tenant", business_id="business")) == 1


def test_competing_same_key_draft_create_cannot_write_second_origin(monkeypatch):
    from application.commerce import phase18_program_publication_registry as program_module

    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    first = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    payload = dict(tenant_id="tenant", business_id="business", actor_id="owner",
                   title="Draft", lessons=[], idempotency_key="same-draft")
    initial = first.create_draft(**payload)
    second = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    _stale_program_registry(monkeypatch, second, initial)
    before = len(events)
    with monkeypatch.context() as time_patch:
        time_patch.setattr(program_module.time, "time", lambda: 2000000000.5)
        with pytest.raises(RuntimeError, match="^program_creation_in_progress$"):
            second.create_draft(**payload)
    assert len(events) == before
    assert first.get(tenant_id="tenant", business_id="business", program_id=initial["id"]) == initial
    assert first.create_draft(**payload) == initial


def test_stale_enrollment_cannot_duplicate_or_poison_customer_timeline(monkeypatch):
    from application.commerce import phase18_program_publication_registry as program_module

    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault(),
    )
    created = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="123456789",
    )
    first = ProgramPublicationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    program = first.publish(
        tenant_id="tenant", business_id="business", actor_id="owner",
        title="Lessons", lessons=[{
            "title": "Introduction", "content_kind": "text", "content_ref": "Hello",
        }], idempotency_key="p",
    )
    payload = dict(
        tenant_id="tenant", business_id="business", actor_id="owner",
        program_id=program["id"], customer_id=created.customer.customer_id,
    )
    initial = first.enroll_customer(**payload)
    second = ProgramPublicationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    monkeypatch.setattr(second, "_enrollments", lambda **_kwargs: [])
    before = len(events)
    with monkeypatch.context() as time_patch:
        time_patch.setattr(program_module.time, "time", lambda: 2000000000.5)
        with pytest.raises(RuntimeError, match="^enrollment_creation_in_progress$"):
            second.enroll_customer(**payload)
    assert len(events) == before
    assert first.enroll_customer(**payload) == initial
    assert len(first.list_enrollments(tenant_id="tenant", business_id="business",
                                      program_id=program["id"])) == 1


def test_identical_lesson_text_cannot_share_approval_between_programs():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault(),
    )
    created = customers.ensure_customer_identity(
        tenant_id="tenant", business_id="business",
        channel="telegram", external_subject="123456789",
    )
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    scope = dict(tenant_id="tenant", business_id="business", actor_id="owner",
                 title="Identical title", lessons=[{
                    "title": "Identical lesson", "content_kind": "link",
                    "content_ref": "https://example.org/lesson",
                 }])
    published_a = programs.publish(**scope, idempotency_key="program-a")
    published_b = programs.publish(**scope, idempotency_key="program-b")
    plans = []
    for program in (published_a, published_b):
        enrolled = programs.enroll_customer(
            tenant_id="tenant", business_id="business", actor_id="owner",
            program_id=program["id"], customer_id=created.customer.customer_id,
        )
        plans.append(programs.lesson_send_plan(
            tenant_id="tenant", business_id="business",
            program_id=program["id"], enrollment_id=enrolled["id"],
            lesson_position=1, channel="telegram",
        ))
    assert plans[0]["recipient"] == plans[1]["recipient"] == "123456789"
    assert plans[0]["program_id"] != plans[1]["program_id"]
    assert plans[0]["text"] != plans[1]["text"]
    assert "Код материала: " in plans[0]["text"]
    assert plans[0]["text"].split("Код материала: ")[0] == plans[1]["text"].split("Код материала: ")[0]
    assert plans[0]["execution_allowed"] is plans[1]["execution_allowed"] is False
