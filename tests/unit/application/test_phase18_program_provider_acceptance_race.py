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
