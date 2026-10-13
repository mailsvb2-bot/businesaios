"""Real canonical Customer/Program facts; no manual path around paid access."""
from __future__ import annotations

import pytest

from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


class AuthoritativeGrant:
    def __init__(self):
        self.enabled = False
        self.calls = []

    def require_access(self, **scope):
        self.calls.append(scope)
        return self.enabled


def _environment():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault(),
    )
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    customer = customers.ensure_customer_identity(
        **scope, channel="telegram", external_subject="1234",
    ).customer
    grant = AuthoritativeGrant()
    paid = ProgramPublicationRegistry(
        event_store=events, idempotency_store=claims,
        customer_registry=customers, paid_access_authority=grant,
    )
    published = paid.publish(
        **scope, actor_id="owner", title="Paid course",
        lessons=[{"title": "A", "content_kind": "link",
                  "content_ref": "https://example.org/lesson"}],
        idempotency_key="paid", access_mode="paid",
    )
    return locals()


def test_paid_program_fails_closed_without_backend_authority_and_without_verified_grant():
    ctx = _environment()
    scope, program, cid = ctx["scope"], ctx["published"], ctx["customer"].customer_id
    missing = ProgramPublicationRegistry(
        event_store=ctx["events"], idempotency_store=ctx["claims"],
        customer_registry=ctx["customers"],
    )
    with pytest.raises(RuntimeError, match="program_paid_access_authority_unavailable"):
        missing.enroll_customer(**scope, actor_id="owner", program_id=program["id"], customer_id=cid)
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        ctx["paid"].enroll_customer(**scope, actor_id="owner",
                                    program_id=program["id"], customer_id=cid)
    assert ctx["paid"].list_enrollments(**scope, program_id=program["id"]) == []
    assert len([e for e in ctx["events"]
                if (e.get("payload") or {}).get("fact_type") == "program.enrollment_created"]) == 0


def test_granted_enrollment_cannot_bypass_revoked_right_at_send_or_provider_outcome():
    ctx = _environment()
    scope, program, cid = ctx["scope"], ctx["published"], ctx["customer"].customer_id
    ctx["grant"].enabled = True
    enrollment = ctx["paid"].enroll_customer(**scope, actor_id="owner",
                                               program_id=program["id"], customer_id=cid)
    assert enrollment["status"] == "awaiting_delivery"
    draft = ctx["paid"].lesson_send_plan(
        **scope, program_id=program["id"], enrollment_id=enrollment["id"],
        lesson_position=1, channel="telegram",
    )
    assert draft["execution_allowed"] is False
    ctx["grant"].enabled = False
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        ctx["paid"].enroll_customer(**scope, actor_id="owner",
                                    program_id=program["id"], customer_id=cid)
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        ctx["paid"].lesson_send_plan(
            **scope, program_id=program["id"], enrollment_id=enrollment["id"],
            lesson_position=1, channel="telegram",
        )
    with pytest.raises(RuntimeError, match="program_paid_entitlement_not_verified"):
        ctx["paid"].record_provider_acceptance(
            **scope, program_id=program["id"], enrollment_id=enrollment["id"],
            lesson_position=1, provider_key="telegram_bot",
            approval_id="approval-1", decision_id="decision-1",
            provider_message_id="message-1", history_id="history-1",
            recorded_at_ms=42,
        )


def test_program_access_mode_is_immutable_per_idempotency_identity():
    ctx = _environment()
    scope = ctx["scope"]
    with pytest.raises(RuntimeError, match="program_idempotency_conflict"):
        ctx["paid"].publish(
            **scope, actor_id="owner", title="Paid course",
            lessons=[{"title": "A", "content_kind": "link",
                      "content_ref": "https://example.org/lesson"}],
            idempotency_key="paid", access_mode="free",
        )
    assert ctx["paid"].get(**scope, program_id=ctx["published"]["id"])["access_mode"] == "paid"


def test_free_program_remains_enrollable_without_psp():
    ctx = _environment()
    scope = ctx["scope"]
    free = ProgramPublicationRegistry(
        event_store=ctx["events"], idempotency_store=ctx["claims"],
        customer_registry=ctx["customers"],
    )
    published = free.publish(
        **scope, actor_id="owner", title="Free course",
        lessons=[{"title": "Free", "content_kind": "text",
                  "content_ref": "Welcome"}],
        idempotency_key="free",
    )
    assert published["access_mode"] == "free"
    receipt = free.enroll_customer(
        **scope, actor_id="owner", program_id=published["id"],
        customer_id=ctx["customer"].customer_id,
    )
    assert receipt["status"] == "awaiting_delivery"
