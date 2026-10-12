"""Phase-18 multi-lesson owner publication over real authentication + canonical EventStore."""
from __future__ import annotations


from dataclasses import replace
from datetime import datetime, timezone

import pytest

from application.commerce.phase18_sale_evidence import evaluate_sale_evidence
from application.lead.registry import LeadRegistry
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService

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




def test_sale_requires_owned_paid_invoice_published_program_and_live_lead():
    events = MemoryEventStore()
    idem = InMemoryIdempotencyStore()
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    lead = leads.create(**scope, lead_id="lead-1", idempotency_key="lead-create")
    program = programs.publish(
        **scope, actor_id="owner", title="Training",
        lessons=[{"title": "Intro", "content_kind": "text", "content_ref": "Lesson"}],
        idempotency_key="program-create",
    )
    invoice = CommercialInvoiceEnvelope(
        **scope, invoice_id="invoice-1", currency="RUB", total_minor=10000,
        metadata={"lead_id": lead.lead_id, "program_id": program["id"]},
    )
    billing = InvoiceLifecycleService()
    invoice = billing.issue(invoice, issued_at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    invoices = {"invoice-1": invoice}
    def read_invoice(*, tenant_id, business_id, invoice_id):
        assert (tenant_id, business_id) == ("tenant-a", "business-a")
        return invoices[invoice_id]
    args = dict(**scope, lead_id="lead-1", program_id=program["id"],
                invoice_id="invoice-1", leads=leads, programs=programs,
                invoice_reader=read_invoice, reversal_reader=lambda **_: False)
    unpaid = evaluate_sale_evidence(**args)
    assert unpaid.can_request_fulfilment is False
    assert unpaid.reason == "payment_not_confirmed"
    invoices["invoice-1"] = billing.record_payment(invoice, amount_minor=4000)
    partial = evaluate_sale_evidence(**args)
    assert partial.can_request_fulfilment is False
    invoices["invoice-1"] = billing.record_payment(invoices["invoice-1"], amount_minor=6000)
    paid = evaluate_sale_evidence(**args)
    assert paid.payment_confirmed and paid.can_request_fulfilment
    assert paid.reason == "ready_for_governed_fulfilment"
    assert len(events) == 2  # read-only gate makes no business facts

    original = invoices["invoice-1"]
    for changed in (
        replace(original, business_id="another-business"),
        replace(original, tenant_id="another-tenant"),
        replace(original, metadata={"lead_id": "different-lead", "program_id": program["id"]}),
        replace(original, metadata={"lead_id": "lead-1", "program_id": "different-program"}),
    ):
        invoices["invoice-1"] = changed
        with pytest.raises(RuntimeError, match="sale_billing_scope_mismatch|sale_invoice_product_binding_missing"):
            evaluate_sale_evidence(**args)
    invoices["invoice-1"] = original
    assert evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: True}).reason == "payment_reversed"
    with pytest.raises(RuntimeError, match="sale_reversal_authority_required"):
        evaluate_sale_evidence(**{**args, "reversal_reader": None})
    with pytest.raises(RuntimeError, match="sale_reversal_evidence_invalid"):
        evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: None})
    invoices["invoice-1"] = replace(original, status=InvoiceLifecycleStatus.CREDITED)
    assert not evaluate_sale_evidence(**args).can_request_fulfilment
    invoices["invoice-1"] = original
    leads.archive(**scope, lead_id="lead-1", idempotency_key="archive")
    assert evaluate_sale_evidence(**args).reason == "lead_inactive"
    with pytest.raises((LookupError, KeyError)):
        evaluate_sale_evidence(**{**args, "business_id": "different-business"})


def test_sale_reads_durable_canonical_invoice_after_registry_restart():
    from billing.invoice_registry import InvoiceRegistry

    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    first_billing = InvoiceRegistry(event_store=events, idempotency_store=idem)
    leads.create(**scope, lead_id="lead-one", idempotency_key="lead-one")
    program = programs.publish(
        **scope, actor_id="owner", title="Paid lessons", idempotency_key="course",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Text"}],
    )
    invoice = CommercialInvoiceEnvelope(
        **scope, invoice_id="invoice-one", currency="RUB",
        total_minor=15000, metadata={"lead_id": "lead-one", "program_id": program["id"]},
    )
    first_billing.create(business_id=scope["business_id"], invoice=invoice, idempotency_key="create")
    first_billing.issue(**scope, invoice_id="invoice-one", idempotency_key="issue",
                        issued_at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    first_billing.record_payment(**scope, invoice_id="invoice-one",
                                 idempotency_key="payment", amount_minor=15000)
    restarted = InvoiceRegistry(event_store=events, idempotency_store=idem)
    args = dict(**scope, lead_id="lead-one", program_id=program["id"],
                invoice_id="invoice-one", leads=leads, programs=programs,
                invoice_reader=restarted.get, reversal_reader=lambda **_: False)
    assert evaluate_sale_evidence(**args).can_request_fulfilment is True
    # A reverse-payment observation from the canonical finance owner overrides
    # the durable paid invoice projection until it has been reconciled.
    assert evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: True}).can_request_fulfilment is False
    restarted.credit(**scope, invoice_id="invoice-one", idempotency_key="credit")
    assert evaluate_sale_evidence(**args).can_request_fulfilment is False
    assert evaluate_sale_evidence(**args).reason == "payment_not_confirmed"
