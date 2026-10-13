"""Verified VK/Telegram webhook → canonical CRM → Conversation → Message → Lead.

Uses the actual provider replay guard and EventStore; no fabricated customer
facts or second lead ledger. Sandbox transports are only used for signatures.
"""
from __future__ import annotations


import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.commerce.phase18_commercial_ingress import CommercialIngressCoordinator
from application.lead.registry import LeadRegistry
from contracts.customer import CustomerNotFound
from contracts.lead import LeadNotFound
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.messaging.conversation_registry import ConversationRegistry
from runtime.messaging.message_registry import MessageRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


class DecisionProcessor:
    def __init__(self):
        self.handoffs = []

    def process(self, *, handoff):
        self.handoffs.append(handoff)
        metadata = dict(handoff["inbound_message"]["metadata"])
        assert metadata["customer_id"]
        assert metadata["conversation_id"]
        assert metadata["lead_id"]
        return {"accepted": True, "decision_envelope": {"decision_id": "decision-" + str(len(self.handoffs))}}


def _wired(monkeypatch, *, verified=True):
    monkeypatch.setattr(
        ProviderWebhookRuntime, "verify", lambda self, **kwargs: verified,
    )
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(
        event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault(),
    )
    conversations = ConversationRegistry(
        event_store=events, idempotency_store=claims, customer_registry=customers,
    )
    messages = MessageRegistry(event_store=events, idempotency_store=claims)
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    processor = DecisionProcessor()
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(claims),
        customer_registry=customers, conversation_registry=conversations,
        message_registry=messages, lead_registry=leads,
        inbound_processor=processor,
    )
    return service, processor, customers, conversations, messages, leads, events, claims


def telegram_body(update_id, msg_id, *, from_id=42):
    return ('{"update_id":%d,"message":{"message_id":%d,"text":"I want a product",'
            '"chat":{"id":%d},"from":{"id":%d}}}' %
            (update_id, msg_id, from_id, from_id)).encode()


def test_two_messages_same_customer_keep_one_canonical_lead_and_no_duplicate_on_retry(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    provider = provider_map()["telegram_bot"]
    one = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(100, 10), event_key="event-100", topic="telegram_update")
    again = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(100, 10), event_key="event-100", topic="telegram_update")
    two = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(101, 11), event_key="event-101", topic="telegram_update")

    first = one.metadata["commercial_lead"]
    second = two.metadata["commercial_lead"]
    assert one.accepted is True and two.accepted is True
    assert again.status == "replayed"
    assert first["lead_id"] == second["lead_id"]
    assert first["customer_id"] == second["customer_id"]
    assert first["conversation_id"] == second["conversation_id"]
    assert first["message_id"] != second["message_id"]
    assert len(processor.handoffs) == 2
    assert len(leads.list_for_business(tenant_id="tenant-a", business_id="business-a")) == 1
    lead = leads.get(tenant_id="tenant-a", business_id="business-a", lead_id=first["lead_id"])
    assert lead.source == "telegram"
    assert lead.status == "new"
    assert lead.customer_id == first["customer_id"]
    assert lead.conversation_id == first["conversation_id"]
    assert lead.channel == "telegram"
    assert customers.find_by_identity(tenant_id="tenant-a", business_id="business-a",
                                      channel="telegram", external_subject="42").customer.customer_id == lead.customer_id
    assert conversations.get(tenant_id="tenant-a", business_id="business-a",
                             conversation_id=lead.conversation_id).activity_count == 2
    assert len(messages.list_for_business(tenant_id="tenant-a", business_id="business-a")) == 2
    # No CRM/PII clone: only fact payloads with stable canonical references.
    lead_facts = [event for event in events if (event.get("payload") or {}).get("fact_type") == "lead.created"]
    assert len(lead_facts) == 1
    assert "I want a product" not in str(lead_facts)


def test_unverified_webhook_never_mutates_any_canonical_owner(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch, verified=False)
    result = service.ingest(provider=provider_map()["telegram_bot"], tenant_id="tenant-a",
        business_id="business-a", headers={}, body=telegram_body(100, 10),
        event_key="event-invalid", topic="telegram_update")
    assert result.status == "invalid_signature"
    assert not events
    assert not processor.handoffs
    assert not leads.list_for_business(tenant_id="tenant-a", business_id="business-a")


def test_same_external_contact_in_another_business_does_not_share_lead(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    provider = provider_map()["telegram_bot"]
    p = telegram_body(100, 10)
    one = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=p, event_key="a-event", topic="telegram_update")
    two = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-b",
        headers={}, body=p, event_key="b-event", topic="telegram_update")
    first = one.metadata["commercial_lead"]
    second = two.metadata["commercial_lead"]
    assert first["lead_id"] != second["lead_id"]
    assert first["customer_id"] != second["customer_id"]
    assert first["conversation_id"] != second["conversation_id"]
    with pytest.raises(LeadNotFound):
        leads.get(tenant_id="tenant-a", business_id="business-b", lead_id=first["lead_id"])
    with pytest.raises(CustomerNotFound):
        customers.get_customer(tenant_id="tenant-a", business_id="business-b",
                               customer_id=first["customer_id"])


def test_archived_lead_never_silently_reopened_and_requires_explicit_recovery(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    provider = provider_map()["telegram_bot"]
    one = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(100, 10), event_key="first", topic="telegram_update")
    lead_id = one.metadata["commercial_lead"]["lead_id"]
    leads.archive(tenant_id="tenant-a", business_id="business-a", lead_id=lead_id,
                  idempotency_key="operator-archived")
    with pytest.raises(ValueError, match="commercial_lead_archived_no_automatic_reopening"):
        service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
            headers={}, body=telegram_body(101, 11), event_key="second", topic="telegram_update")
    assert len(leads.list_for_business(tenant_id="tenant-a", business_id="business-a")) == 1
    assert len(processor.handoffs) == 1


def test_canonical_lead_rejects_foreign_conversation_or_message(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    provider = provider_map()["telegram_bot"]
    one = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(100, 10, from_id=42), event_key="first", topic="telegram_update")
    two = service.ingest(provider=provider, tenant_id="tenant-a", business_id="business-a",
        headers={}, body=telegram_body(101, 11, from_id=88), event_key="second", topic="telegram_update")
    first = one.metadata["commercial_lead"]
    second = two.metadata["commercial_lead"]
    bridge = CommercialIngressCoordinator(
        customers=customers, conversations=conversations, messages=messages, leads=leads,
    )
    with pytest.raises(ValueError, match="commercial_ingress_canonical_binding_mismatch"):
        bridge.ensure_verified_ingress(
            tenant_id="tenant-a", business_id="business-a",
            customer_id=first["customer_id"], conversation_id=second["conversation_id"],
            message_id=first["message_id"], channel="telegram",
        )
    with pytest.raises(ValueError, match="commercial_ingress_canonical_binding_mismatch"):
        bridge.ensure_verified_ingress(
            tenant_id="tenant-a", business_id="business-a",
            customer_id=first["customer_id"], conversation_id=first["conversation_id"],
            message_id=second["message_id"], channel="telegram",
        )
    assert len(leads.list_for_business(tenant_id="tenant-a", business_id="business-a")) == 2


def test_lead_binding_survives_status_change_and_is_immutable(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    one = service.ingest(provider=provider_map()["telegram_bot"],
        tenant_id="tenant-a", business_id="business-a", headers={},
        body=telegram_body(100, 10), event_key="first", topic="telegram_update")
    original = one.metadata["commercial_lead"]
    qualified = leads.update(tenant_id="tenant-a", business_id="business-a",
                             lead_id=original["lead_id"], idempotency_key="qualified", status="qualified")
    assert qualified.status == "qualified"
    assert qualified.customer_id == original["customer_id"]
    assert qualified.conversation_id == original["conversation_id"]
    two = service.ingest(provider=provider_map()["telegram_bot"],
        tenant_id="tenant-a", business_id="business-a", headers={},
        body=telegram_body(101, 11), event_key="second", topic="telegram_update")
    assert two.metadata["commercial_lead"]["lead_id"] == original["lead_id"]
    assert two.metadata["commercial_lead"]["sales_stage"] == "qualified"
    with pytest.raises(ValueError, match="already exists with different identity"):
        leads.create(
            tenant_id="tenant-a", business_id="business-a", lead_id=original["lead_id"],
            idempotency_key="rewrite", source="telegram", status="qualified",
            customer_id="alien", conversation_id=original["conversation_id"],
            channel="telegram",
        )


def test_same_transport_contact_reused_in_distinct_chats_has_separate_claims(monkeypatch):
    service, processor, customers, conversations, messages, leads, events, claims = _wired(monkeypatch)
    tenant, business = "tenant-a", "business-a"
    record = customers.ensure_customer_identity(
        tenant_id=tenant, business_id=business, channel="telegram", external_subject="42",
    )
    customer_id = record.customer.customer_id
    first = conversations.ensure_ingress(
        tenant_id=tenant, business_id=business, customer_id=customer_id,
        channel="telegram", route_ref="chat:private", contact_id="message:1",
    )
    second = conversations.ensure_ingress(
        tenant_id=tenant, business_id=business, customer_id=customer_id,
        channel="telegram", route_ref="chat:group", contact_id="message:1",
    )
    assert first.conversation_id != second.conversation_id
    assert conversations.get(
        tenant_id=tenant, business_id=business, conversation_id=first.conversation_id,
    ).activity_count == 1
    assert conversations.get(
        tenant_id=tenant, business_id=business, conversation_id=second.conversation_id,
    ).activity_count == 1
    # Retry is idempotent in the same conversation and never changes
    # another conversation's activity.
    replay = conversations.ensure_ingress(
        tenant_id=tenant, business_id=business, customer_id=customer_id,
        channel="telegram", route_ref="chat:private", contact_id="message:1",
    )
    assert replay.activity_count == 1
