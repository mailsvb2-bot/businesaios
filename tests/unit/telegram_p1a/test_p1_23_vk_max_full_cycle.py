"""P1-23: VK/MAX full cycle — webhook → authenticity → recipient → customer →
decision → outbound → provider → receipt, on the real ingress and egress code.

Only the network and the DecisionCore gateway are stand-ins: the processor plays
the decision (returns one reply to the verified sender) and the provider HTTP
answer is a canned body in the provider's documented response shape.
"""

from __future__ import annotations

import json

import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.lead.registry import LeadRegistry
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_http_live_clients import VendorHttpLiveTransport
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.conversation_registry import ConversationRegistry
from runtime.messaging.message_registry import MessageRegistry
from runtime.messaging.outbound_message import OutboundMessage
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault

T, B, SECRET = "tenant-a", "biz-a", "bridge-secret-0123456789"


def _vault(provider_key: str) -> InMemorySecretVault:
    vault, provider = InMemorySecretVault(), provider_map()[provider_key]
    for name, value in (("webhook_secret", SECRET), ("access_token", "provider-token")):
        ref = SecretRef(tenant_id=T, connector_id=provider.connector_id, scope=B,
                        secret_name=f"{provider.connector_id}.{name}")
        vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR), plaintext=value.encode())
    return vault


class Decision:
    """Stand-in for the inbound DecisionCore gateway: one reply to the verified sender."""

    def __init__(self):
        self.handoffs = []

    def process(self, *, handoff):
        self.handoffs.append(handoff)
        return {"accepted": True, "decision_envelope": {"decision_id": f"dec-{len(self.handoffs)}"}}


class _OfflineTransport(VendorHttpLiveTransport):
    def _load_secrets(self, **kw):
        return {"access_token": "provider-token"}

    def _render_url(self, **kw):
        return "https://provider.example/send"

    def _build_headers(self, **kw):
        return {}


class ProviderService:
    """Queue + live transport with the network replaced by a canned provider answer."""

    def __init__(self, provider_key, answer):
        self.provider_registry = type("R", (), {"get": staticmethod(lambda key: provider_map()[key])})()
        self.provider_key, self.answer, self.requests = provider_key, answer, []

    def execute_queued_provider_sync(self, *, payload, **kwargs):
        transport = _OfflineTransport.__new__(_OfflineTransport)
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        self.requests.append(transport._prepare_request(provider=provider_map()[self.provider_key], tenant_id=T,
                                                        business_id=B, operation="message_send", payload=clean, binding={}))
        parsed = ProviderResponseParsers().parse(provider=provider_map()[self.provider_key], operation="message_send",
                                                 response={"http_status": 200, "response_body": json.dumps(self.answer),
                                                           "response_headers": {}})
        return {"dispatch": {"queued": True, "job_id": "job-1"},
                "result": {"accepted": True, "status": "live_executed", "parsed_response": parsed}}


def _wired(provider_key):
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    customers = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault())
    conversations = ConversationRegistry(event_store=events, idempotency_store=claims, customer_registry=customers)
    decision = Decision()
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(_vault(provider_key)), replay_guard=ProviderWebhookReplayGuard(claims),
        customer_registry=customers, conversation_registry=conversations,
        message_registry=MessageRegistry(event_store=events, idempotency_store=claims),
        lead_registry=LeadRegistry(event_store=events, idempotency_store=claims), inbound_processor=decision)
    return service, decision, customers, events


CASES = {
    "vk_messaging": dict(
        channel="vk", topic="message_new", headers={},
        body=lambda secret: {"type": "message_new", "group_id": 1, "event_id": "vk-evt-1", "secret": secret,
                             "object": {"message": {"id": 77, "from_id": 700001, "peer_id": 700001, "text": "Сколько стоит?"}}},
        answer={"response": 4242}, recipient=("form_body", "peer_id")),
    "max_messaging": dict(
        channel="max", topic="message_created", headers=lambda secret: {"X-Max-Bot-Api-Secret": secret},
        body=lambda secret: {"update_type": "message_created", "timestamp": 1787259600000,
                             "message": {"sender": {"user_id": 778899, "name": "Анна"}, "recipient": {"user_id": 778899},
                                         "body": {"mid": "mid.in.1", "text": "Сколько стоит?"}}},
        answer={"message": {"recipient": {"user_id": 778899}, "timestamp": 1,
                            "body": {"mid": "mid.out.1", "seq": 1, "text": "ok"}}},
        recipient=("url_or_body", "user_id")),
}


def _ingest(service, provider_key, secret):
    case = CASES[provider_key]
    headers = case["headers"](secret) if callable(case["headers"]) else case["headers"]
    return service.ingest(provider=provider_map()[provider_key], tenant_id=T, business_id=B, headers=headers,
                          body=json.dumps(case["body"](secret)).encode(), event_key="", topic=case["topic"],
                          owner_id="provider_admin")


@pytest.mark.parametrize("provider_key", sorted(CASES))
def test_full_cycle_from_signed_webhook_to_provider_receipt(provider_key):
    case = CASES[provider_key]
    service, decision, customers, _ = _wired(provider_key)
    result = _ingest(service, provider_key, SECRET)
    assert result.accepted and result.status == "accepted"
    assert service.transport_ack_safe(result)

    inbound = decision.handoffs[0]["inbound_message"]
    sender = str(inbound["user_id"])
    meta = inbound["metadata"]
    assert inbound["channel"] == case["channel"] and inbound["text"] == "Сколько стоит?"
    found = customers.find_by_identity(tenant_id=T, business_id=B, channel=case["channel"], external_subject=sender)
    assert found.customer.customer_id == meta["customer_id"] and meta["conversation_id"] and meta["lead_id"]

    provider = ProviderService(provider_key, case["answer"])
    reply = OutboundMessage(decision_id="dec-1", correlation_id=inbound["correlation_id"], tenant_id=T, business_id=B,
                            user_id=sender, channel=case["channel"], text="Цена 990 ₽",
                            track_payload={"_provider_native": {"business_id": B}})
    delivery = _NativeProviderQueueAdapter(case["channel"], service_factory=lambda: provider).send(reply)
    request = provider.requests[0]
    body = request.get("form_body") or request.get("json_body")
    if provider_key == "vk_messaging":
        assert body["peer_id"] == sender and body["message"] == "Цена 990 ₽"
    else:
        assert body == {"text": "Цена 990 ₽"}
    assert delivery.ok and delivery.mode == "accepted"
    assert delivery.external_id == {"vk_messaging": "4242", "max_messaging": "mid.out.1"}[provider_key]


@pytest.mark.parametrize("provider_key", sorted(CASES))
def test_forged_webhook_never_reaches_customer_or_decision(provider_key):
    service, decision, _, events = _wired(provider_key)
    result = _ingest(service, provider_key, "wrong-secret")
    assert result.status == "invalid_signature" and not result.accepted
    assert not decision.handoffs and not list(events)


@pytest.mark.parametrize("provider_key", sorted(CASES))
def test_provider_retry_does_not_decide_twice(provider_key):
    service, decision, _, _ = _wired(provider_key)
    first = _ingest(service, provider_key, SECRET)
    again = _ingest(service, provider_key, SECRET)
    assert first.status == "accepted" and again.status == "replayed"
    assert len(decision.handoffs) == 1 and service.transport_ack_safe(again)
