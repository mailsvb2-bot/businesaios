from __future__ import annotations

import hashlib
import json

from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def test_lowercase_http_headers_and_legacy_fallback_use_signed_stable_multichannel_event_key(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.webhook_secret')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=b'secret')
    body = json.dumps({'object': {'message': {'from_id': 7, 'text': 'hello', 'id': 9}}}, sort_keys=True).encode()
    service = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(vault), replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()))
    result = service.ingest(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'x-businessaios-webhook-secret': 'secret'}, body=body, event_key='payload-digest-fallback')
    assert result.accepted is True
    assert result.event_key == f"vk_messaging:{hashlib.sha256(body).hexdigest()[:24]}"


def test_vk_max_authenticated_ingress_scopes_signed_reply_to_real_event(tmp_path, monkeypatch) -> None:
    from application.decision_runtime.flow import build_payload
    from core.policies.telegram.helpers import ProposedAction
    from core.safety.controls.action_budget.models import is_routine_reply
    from runtime.messaging.inbound_message import InboundMessage
    from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", "integration-test-only-strong-secret")
    bodies = {
        "vk_messaging": {"type": "message_new", "object": {"message": {
            "id": 9, "from_id": 777, "peer_id": 777, "text": "hello"}}},
        "max_messaging": {"update_type": "message_created", "message": {
            "sender": {"user_id": 777}, "recipient": {"chat_id": 777},
            "body": {"mid": "max-msg-9", "text": "hello"}}},
    }
    for provider_key, body_dict in bodies.items():
        provider = provider_map()[provider_key]
        vault = InMemorySecretVault()
        ref = SecretRef(tenant_id="tenant-a", connector_id=provider.connector_id,
                        scope="business-a", secret_name=f"{provider.connector_id}.webhook_secret")
        vault.seed_plaintext(ref=ref, plaintext="provider-secret")
        class Processor:
            calls = 0
            proof = None
            payload = None

            def process(self, *, handoff):
                self.calls += 1
                inbound = handoff["inbound_message"]
                state = map_inbound_to_world_state(InboundMessage(
                    tenant_id=inbound["tenant_id"], channel=inbound["channel"],
                    user_id=inbound["user_id"], text=inbound["text"],
                    transport_message_id=inbound["transport_message_id"],
                    metadata={"chat_id": inbound["chat_id"]},
                ))
                _, self.payload = build_payload(
                    state=state, out=ProposedAction("send_message@v1", {
                        "user_id": inbound["user_id"], "text": "reply",
                    }), pinned_world_model_meta={}, tenant_id=inbound["tenant_id"],
                    product_id=None, domain=None, product_version=None, actor_id=inbound["user_id"],
                )
                assert self.payload["channel"] == inbound["channel"]
                assert self.payload["chat_id"] == inbound["chat_id"]
                self.proof = self.payload.get("meta", {}).get("inbound_user_reply")
                return {"accepted": True, "decision_envelope": "canonical"}
        processor = Processor()
        service = ProviderInboundWebhookService(
            webhook_runtime=ProviderWebhookRuntime(vault),
            replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
            inbound_processor=processor,
        )
        request = dict(provider=provider, tenant_id="tenant-a", business_id="business-a",
                       headers={"x-businessaios-webhook-secret": "provider-secret"},
                       body=json.dumps(body_dict).encode(), event_key=f"{provider_key}-event")
        invalid = service.ingest(**{**request, "headers": {"x-businessaios-webhook-secret": "wrong"}})
        assert invalid.status == "invalid_signature" and processor.calls == 0
        cross_tenant = service.ingest(**{**request, "tenant_id": "tenant-b"})
        assert cross_tenant.status == "invalid_signature" and processor.calls == 0
        accepted = service.ingest(**request)
        assert accepted.accepted and processor.calls == 1
        assert processor.proof is not None and is_routine_reply("send_message@v1", processor.payload)
        assert not is_routine_reply("send_message@v1", {**processor.payload, "text": "unsolicited"})
        replay = service.ingest(**request)
        assert not replay.accepted and processor.calls == 1


def test_public_http_rejects_pending_single_event_replay_without_handoff() -> None:
    """A pending replay cannot be HTTP-acknowledged just because no work is handed off."""
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    from adapters.api.fastapi.provider_webhook_routes import register_provider_webhook_routes

    class Handlers:
        def __init__(self, safe):
            self.safe = safe
            self.calls = 0

        def ingest_provider_webhook(self, *, payload):
            self.calls += 1
            assert payload["provider_key"] == "max_messaging"
            return {
                "status": "replayed",
                "accepted": False,
                "transport_ack_safe": self.safe,
                "metadata": {
                    "decision": {"resolution": "replay_pending" if not self.safe else "replay_completed"},
                    "messaging_handoff": {},
                    "batch_results": (),
                },
            }

    for is_safe, expected_status in ((False, 503), (True, 200)):
        handlers = Handlers(is_safe)
        router = APIRouter()
        register_provider_webhook_routes(router=router, provider_admin_handlers=handlers)
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post(
                "/providers/webhook/tenant-a/biz-a/max_messaging",
                json={"update_type": "message_created"},
            )
        assert response.status_code == expected_status
        assert handlers.calls == 1
        if not is_safe:
            assert response.json()["detail"] == "provider_webhook_processing_incomplete"
