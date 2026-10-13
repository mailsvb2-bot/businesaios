"""Real canonical sales snapshot: no PII, no stale AI actions, no false payments."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_context import CommercialJourneyContextReader
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from contracts.messaging_event_identity import MessageDirection, MessageIdentity
from core.offers.offer_types import OfferSummary
from crm.customer_registry import CustomerRegistry
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.messaging.conversation_registry import ConversationRegistry
from runtime.messaging.message_registry import MessageRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


class Offers:
    def resolve(self, *, key):
        return SimpleNamespace(id="catalog@v1", list_offers=lambda: [OfferSummary(
            offer_id="verified", title="Published", base_price_rub=400,
            meta={"program_id": key.product_id, "business_id": key.business_id},
        )])


def _build():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    customers = CustomerRegistry(event_store=events, idempotency_store=claims,
                                 pii_vault=InMemorySecretVault())
    customer = customers.ensure_customer_identity(
        **scope, channel="telegram", external_subject="123",
    ).customer
    conversations = ConversationRegistry(event_store=events, idempotency_store=claims,
                                         customer_registry=customers)
    conversation = conversations.ensure_ingress(
        **scope, customer_id=customer.customer_id, channel="telegram",
        route_ref="chat:123", contact_id="message:1",
    )
    messages = MessageRegistry(event_store=events, idempotency_store=claims)
    first = messages.record(
        identity=MessageIdentity(message_id="message:1", **scope, channel="telegram",
                                 direction=MessageDirection.INBOUND),
        customer_id=customer.customer_id, conversation_id=conversation.conversation_id,
    )
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    lead = leads.create(
        **scope, lead_id="canonical-lead", idempotency_key="create-lead",
        customer_id=customer.customer_id, conversation_id=conversation.conversation_id,
        channel="telegram", source="telegram", status="new",
    )
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims,
                                          customer_registry=customers)
    published = programs.publish(
        access_mode="paid",
        **scope, actor_id="owner", title="Course", idempotency_key="create-program",
        lessons=[{"title": "Start", "content_kind": "text", "content_ref": "Material"}],
    )
    orders = OrderStore(event_store=events)
    invoices = InvoiceRegistry(event_store=events, idempotency_store=claims)
    context = CommercialJourneyContextReader(
        leads=leads, customers=customers, conversations=conversations,
        messages=messages, programs=programs, orders=orders, invoices=invoices,
    )
    purchase = CommercialProgramPurchaseService(
        leads=leads, customers=customers, programs=programs,
        offers=Offers(), orders=orders, invoices=invoices,
    )
    return locals()


def test_snapshot_detects_message_price_invoice_and_stage_changes():
    ctx = _build()
    scope = ctx["scope"]
    service = ctx["context"]
    lead_id = ctx["lead"].lead_id
    before = service.read(**scope, lead_id=lead_id)
    assert before.inbound_message_count == 1
    assert before.latest_message_id == ctx["first"].message_id
    assert before.sales_stage == "new"
    assert before.active_program_ids == (ctx["published"]["id"],)
    assert before.orders == ()
    assert before.can_prepare_offer is True
    assert service.require_current(**scope, lead_id=lead_id,
                                   expected_fingerprint=before.context_fingerprint) == before

    ctx["leads"].update(**scope, lead_id=lead_id, status="qualified",
                        idempotency_key="qualify")
    with pytest.raises(RuntimeError, match="commercial_context_stale_decision"):
        service.require_current(**scope, lead_id=lead_id,
                                expected_fingerprint=before.context_fingerprint)
    new_stage = service.read(**scope, lead_id=lead_id)
    assert new_stage.sales_stage == "qualified"

    order = ctx["purchase"].prepare_purchase(
        **scope, lead_id=lead_id, customer_id=ctx["customer"].customer_id,
        program_id=ctx["published"]["id"], offer_id="verified",
        idempotency_key="buy-program",
    )
    with_order = service.read(**scope, lead_id=lead_id)
    assert len(with_order.orders) == 1
    snapshot_order = with_order.orders[0]
    assert snapshot_order.order_id == order.order_id
    assert snapshot_order.billing_status == "issued"
    assert snapshot_order.external_payment_verified is False
    assert snapshot_order.delivery_verified is False
    assert snapshot_order.paid_minor == 0
    ctx["invoices"].record_payment(**scope, invoice_id=order.invoice_id,
                                   amount_minor=order.amount_minor, idempotency_key="settled")
    after_invoice = service.read(**scope, lead_id=lead_id)
    assert after_invoice.context_fingerprint != with_order.context_fingerprint
    assert after_invoice.orders[0].billing_status == "paid"
    assert after_invoice.orders[0].external_payment_verified is False


def test_snapshot_rejects_foreign_lead_and_closed_conversation():
    ctx = _build()
    scope, reader = ctx["scope"], ctx["context"]
    lead = ctx["lead"]
    with pytest.raises(LookupError):
        reader.read(tenant_id="tenant-a", business_id="business-b", lead_id=lead.lead_id)
    expected = reader.read(**scope, lead_id=lead.lead_id)
    ctx["leads"].archive(**scope, lead_id=lead.lead_id, idempotency_key="archive")
    with pytest.raises(RuntimeError, match="commercial_context_customer_or_conversation_closed"):
        reader.require_current(**scope, lead_id=lead.lead_id,
                               expected_fingerprint=reader.read(**scope, lead_id=lead.lead_id).context_fingerprint)
    with pytest.raises(RuntimeError, match="commercial_context_stale_decision"):
        reader.require_current(**scope, lead_id=lead.lead_id,
                               expected_fingerprint=expected.context_fingerprint)


def test_canonical_funnel_advisory_uses_live_customer_and_order_facts_not_fake_payment():
    ctx = _build()
    reader, scope, lead = ctx["context"], ctx["scope"], ctx["lead"]
    first = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert first["derived_stage"] == "engaged"
    assert first["advisory_only"] is True
    assert first["externally_verified_payment"] is False
    ctx["leads"].update(**scope, lead_id=lead.lead_id, status="qualified",
                        idempotency_key="advisory-stage-qualified")
    qualified = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert qualified["derived_stage"] == "qualified"
    assert qualified["context_fingerprint"] != first["context_fingerprint"]
    order = ctx["purchase"].prepare_purchase(
        **scope, lead_id=lead.lead_id, customer_id=ctx["customer"].customer_id,
        program_id=ctx["published"]["id"], offer_id="verified",
        idempotency_key="advisory-create-order",
    )
    ctx["invoices"].record_payment(**scope, invoice_id=order.invoice_id,
                                   amount_minor=order.amount_minor,
                                   idempotency_key="advisory-unverified-invoice")
    after = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert after["has_order"] is True
    assert after["externally_verified_payment"] is False
    assert after["derived_stage"] != "won"
    with pytest.raises(LookupError):
        reader.read_funnel_advisory(
            tenant_id=scope["tenant_id"], business_id="foreign-business",
            lead_id=lead.lead_id,
        )



@pytest.mark.parametrize(
    ("signals", "reason", "priority"),
    [
        ({"sensitive_context": True, "human_requested": True}, "sensitive_context", "urgent"),
        ({"human_requested": True}, "explicit_human_request", "high"),
        ({"pricing_exception": True}, "pricing_exception", "high"),
        ({"failed_attempts": 2}, "repeated_failure", "high"),
        ({"negative_sentiment": True}, "negative_sentiment", "normal"),
        ({"model_confidence": 0.5}, "low_confidence", "normal"),
    ],
)
def test_clientplatform_sales_handoff_uses_canonical_operator_contract(signals, reason, priority):
    ctx = _build()
    scope = ctx["scope"]
    reader = ctx["context"]
    before = reader.read(**scope, lead_id=ctx["lead"].lead_id)
    review = reader.evaluate_sales_engagement(
        **scope, lead_id=ctx["lead"].lead_id,
        expected_fingerprint=before.context_fingerprint,
        model_confidence=signals.pop("model_confidence", 0.98), **signals,
    )
    assert review["handoff_reason"] == reason
    assert review["handoff_priority"] == priority
    assert review["handoff"]["operator_required"] is True
    assert review["handoff"]["handoff_state"] == "awaiting_operator"
    assert review["handoff"]["decision_id"] == before.context_fingerprint
    assert review["outreach_suppressed"] is True
    assert review["followup_queued"] is False
    assert review["operator_handoff_persisted"] is False
    assert review["message_sent"] is False


def test_sales_followup_candidate_is_not_a_message_send_or_approval():
    ctx = _build()
    scope = ctx["scope"]
    reader = ctx["context"]
    before = reader.read(**scope, lead_id=ctx["lead"].lead_id)
    decision = reader.evaluate_sales_engagement(
        **scope, lead_id=ctx["lead"].lead_id,
        expected_fingerprint=before.context_fingerprint,
        model_confidence=0.99,
    )
    assert decision["followup_candidate"] is True
    assert decision["message_sent"] is False
    assert decision["followup_queued"] is False
    assert decision["manual_approval_required"] is True
    opted_out = reader.evaluate_sales_engagement(
        **scope, lead_id=ctx["lead"].lead_id,
        expected_fingerprint=before.context_fingerprint,
        model_confidence=0.99, customer_opted_out=True,
    )
    assert opted_out["followup_candidate"] is False
    assert opted_out["handoff"] is None
    assert opted_out["suppression_reason"] == "customer_opt_out"
    ctx["purchase"].prepare_purchase(
        **scope, lead_id=ctx["lead"].lead_id,
        customer_id=ctx["customer"].customer_id,
        program_id=ctx["published"]["id"], offer_id="verified",
        idempotency_key="followup-existing-order",
    )
    with pytest.raises(RuntimeError, match="commercial_context_stale_decision"):
        reader.evaluate_sales_engagement(
            **scope, lead_id=ctx["lead"].lead_id,
            expected_fingerprint=before.context_fingerprint,
            model_confidence=0.99,
        )
    after = reader.read(**scope, lead_id=ctx["lead"].lead_id)
    new_review = reader.evaluate_sales_engagement(
        **scope, lead_id=ctx["lead"].lead_id,
        expected_fingerprint=after.context_fingerprint,
        model_confidence=0.99,
    )
    assert new_review["suppression_reason"] == "existing_order_requires_billing_truth"


@pytest.mark.parametrize("input_overrides", [
    {"model_confidence": float("nan")},
    {"model_confidence": float("inf")},
    {"model_confidence": -0.1},
    {"model_confidence": 1.1},
    {"model_confidence": True},
    {"failed_attempts": -1},
    {"failed_attempts": True},
    {"human_requested": 1},
    {"customer_opted_out": "yes"},
])
def test_sales_engagement_rejects_invalid_model_and_flags(input_overrides):
    ctx = _build()
    scope = ctx["scope"]
    reader = ctx["context"]
    before = reader.read(**scope, lead_id=ctx["lead"].lead_id)
    with pytest.raises(ValueError):
        reader.evaluate_sales_engagement(
            **scope, lead_id=ctx["lead"].lead_id,
            expected_fingerprint=before.context_fingerprint,
            **({"model_confidence": 0.99} | input_overrides),
        )


def test_sales_engagement_never_exposes_foreign_business_context():
    ctx = _build()
    before = ctx["context"].read(**ctx["scope"], lead_id=ctx["lead"].lead_id)
    with pytest.raises(LookupError):
        ctx["context"].evaluate_sales_engagement(
            tenant_id="tenant-a", business_id="foreign-business",
            lead_id=ctx["lead"].lead_id,
            expected_fingerprint=before.context_fingerprint,
            model_confidence=0.99,
        )



def test_commercial_followup_approved_subject_hash_binding_is_stable():
    import hashlib
    import json

    payload = {
        "provider_key": "telegram_bot",
        "payload": {"chat_id": "user-a", "text": "Approved follow-up"},
    }
    subject = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    assert len(subject) == 64
    assert hashlib.sha256(json.dumps(
        {"provider_key": payload["provider_key"], "payload": {
            **payload["payload"], "text": "Tampered follow-up",
        }},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest() != subject



def test_owner_approved_followup_routes_to_canonical_provider_and_blocks_replay_tampering(tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace

    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
    from adapters.api.fastapi.business_workspace_commercial_routes import (
        register_business_workspace_commercial_routes,
    )
    from entrypoints.api.api_key_policy import ApiKeyPolicy, PersistentApiKeyStore
    from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle

    ctx = _build()
    policy = ApiKeyPolicy(store=PersistentApiKeyStore(
        path=tmp_path / "keys.json", pepper="followup-approval-test",
    ))
    _, owner = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-a", subject="owner-a",
    )
    _, alien = policy.issue_owner_session(
        tenant_id="tenant-a", business_id="business-b", subject="owner-b",
    )
    auth = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=policy),
        security_guard=ApiSecurityOwnerBundle.default(
            audit_path=tmp_path / "audit.jsonl",
        ).api_surface_guard,
    )
    before = ctx["context"].read(**ctx["scope"], lead_id=ctx["lead"].lead_id)
    subject = {
        "provider_key": "telegram_bot",
        "payload": {"chat_id": "123", "text": "A reviewed followup"},
    }
    digest = hashlib.sha256(json.dumps(
        subject, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    binding = {
        **ctx["scope"], "lead_id": ctx["lead"].lead_id,
        "customer_id": before.customer_id,
        "conversation_id": before.conversation_id,
        "channel": before.channel,
        "context_fingerprint": before.context_fingerprint,
        "approved_provider_subject_sha256": digest,
    }
    metadata = {
        "decision_id": "decision-a",
        "action_name": "provider.telegram_bot.message_send",
        "approval_resume_context": {**subject, "business_id": "business-a",
                                     "operation": "message_send"},
    }
    from application.business_autonomy.provider_catalog import provider_map
    from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
    from runtime.queue.job_contract import JobState
    from runtime.queue.job_store_sqlite import SqliteJobStore
    from security.secret_vault import InMemorySecretVault

    calls = []
    durable_store = SqliteJobStore(tmp_path / "real-provider-queue.sqlite3")

    class ApprovedGuard:
        def evaluate(self, **kwargs):
            return SimpleNamespace(
                allowed=True, status="allowed_live_write_operation",
                metadata={"approval": {"subject_fingerprint": digest}},
                to_metadata=lambda: {"approval": {"subject_fingerprint": digest}},
            )

    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=SimpleNamespace(),
        store=durable_store, write_guard=ApprovedGuard(),
    )

    class Provider:
        def approval_store_factory(self):
            return SimpleNamespace(get=lambda key: SimpleNamespace(
                status=SimpleNamespace(value="approved"),
                request=SimpleNamespace(tenant_id="tenant-a", metadata=metadata),
            ) if key == "approval-a" else None)

        def decision_loader(self, **kwargs):
            return SimpleNamespace(decision=SimpleNamespace(
                decision_id="decision-a", action="send_message@v1",
                payload={"commercial_followup": binding},
            ))

        def resolve_approved_message_business_id(self, **kwargs):
            return "business-a"

        def resume_approved_message(self, **kwargs):
            calls.append(kwargs)
            accepted = queue.enqueue_sync(
                provider=provider_map()["telegram_bot"],
                tenant_id=kwargs["tenant_id"], business_id="business-a",
                operation="message_send", mode="live",
                payload=metadata["approval_resume_context"]["payload"],
            )
            return {"execution": {
                "dispatch": {"queued": accepted.queued, "job_id": accepted.job_id},
                "result": {"accepted": False, "status": "durably_queued"},
            }}

    router = APIRouter()
    register_business_workspace_commercial_routes(
        router=router, auth_bundle=auth, purchases=ctx["purchase"],
        context_reader=ctx["context"], provider_handlers=Provider(),
    )
    app = FastAPI()
    app.include_router(router)
    path = "/business-workspace/commercial/leads/canonical-lead/approved-followups/approval-a/deliver"
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post(path).status_code == 401
        assert client.post(path, headers={"X-API-Key": alien}).status_code == 403
        assert client.post(path, headers={"X-API-Key": owner},
                           json={"text": "tampered"}).status_code == 422
        assert calls == []
        response = client.post(path, headers={"X-API-Key": owner})
        assert response.status_code == 200, response.text
        assert response.json()["canonical_provider_execution"]["execution"]["result"]["accepted"] is False
        assert response.json()["delivery_confirmed"] is False
        assert response.json()["delivery_state"] == "queued_or_unconfirmed"
        assert calls == [{"tenant_id": "tenant-a", "approval_id": "approval-a"}]
        job_id = response.json()["canonical_provider_execution"]["execution"]["dispatch"]["job_id"]
        assert durable_store.get(tenant_id="tenant-a", job_id=job_id).state is JobState.PENDING
        reopened = SqliteJobStore(tmp_path / "real-provider-queue.sqlite3")
        assert reopened.get(tenant_id="tenant-a", job_id=job_id).state is JobState.PENDING
        duplicate = client.post(path, headers={"X-API-Key": owner})
        assert duplicate.status_code == 200
        assert duplicate.json()["canonical_provider_execution"]["execution"]["dispatch"]["job_id"] == job_id
        assert reopened.count(tenant_id="tenant-a", queue_name="provider_sync", state=JobState.PENDING) == 1
        assert len(calls) == 2
        metadata["approval_resume_context"]["payload"]["text"] = "tampered"
        assert client.post(path, headers={"X-API-Key": owner}).status_code == 403
        assert len(calls) == 2
        metadata["approval_resume_context"]["payload"]["text"] = "A reviewed followup"
        ctx["leads"].update(**ctx["scope"], lead_id=ctx["lead"].lead_id,
                            status="qualified", idempotency_key="after-approval")
        assert client.post(path, headers={"X-API-Key": owner}).status_code == 409
        assert len(calls) == 2
        ctx["leads"].update(**ctx["scope"], lead_id=ctx["lead"].lead_id,
                            status="do_not_contact", idempotency_key="after-optout")
        newest = ctx["context"].read(**ctx["scope"], lead_id=ctx["lead"].lead_id)
        binding["context_fingerprint"] = newest.context_fingerprint
        assert client.post(path, headers={"X-API-Key": owner}).status_code == 403
        assert len(calls) == 2
