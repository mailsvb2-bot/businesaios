from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_vault import InMemorySecretVault


class _Processor:
    def __init__(self) -> None:
        self.calls = 0

    def process(self, *, handoff):
        self.calls += 1
        return {'accepted': True, 'decision_envelope': {'decision_id': 'd1'}, 'handoff_seen': bool(handoff)}


def test_provider_inbound_webhook_service_runs_inbound_processor_for_accepted_messaging_webhook(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    runtime = ProviderWebhookRuntime(None)
    processor = _Processor()
    service = ProviderInboundWebhookService(
        webhook_runtime=runtime,
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=processor,
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')

    inbound = out.metadata['messaging_inbound_result']
    assert inbound['accepted'] is True
    assert inbound['decision_envelope']['decision_id'] == 'd1'
    replay = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')
    assert replay.status == 'replayed' and replay.metadata['decision']['resolution'] == 'replay_completed'
    assert processor.calls == 1


def test_provider_inbound_webhook_service_does_not_complete_unprocessed_handoff(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(None), replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()))
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    first = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-unprocessed', topic='telegram_update', owner_id='provider_admin')
    retry = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-unprocessed', topic='telegram_update', owner_id='provider_admin')
    assert first.status == 'accepted' and first.metadata['messaging_handoff'] and not first.metadata['messaging_inbound_result']
    assert retry.status == 'replayed' and retry.metadata['decision']['resolution'] == 'rejected_in_progress'


def test_provider_inbound_webhook_projects_one_customer_before_decision_handoff(monkeypatch):
    from crm import CustomerRegistry, CustomerTimelineProjector
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault())

    class _CustomerAwareProcessor:
        def __init__(self):
            self.customer_ids = []
        def process(self, *, handoff):
            self.customer_ids.append(handoff['inbound_message']['metadata']['customer_id'])
            return {'accepted': True, 'decision_envelope': {'decision_id': 'd-customer'}}

    processor = _CustomerAwareProcessor()
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(claims),
        inbound_processor=processor,
        customer_registry=registry,
    )
    body = b'{"message":{"from":{"id":42,"username":"anna"},"text":"hello","message_id":9},"update_id":123}'
    first = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-customer', topic='telegram_update', owner_id='provider_admin')
    replay = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-customer', topic='telegram_update', owner_id='provider_admin')

    customer_id = first.metadata['customer']['customer_id']
    assert processor.customer_ids == [customer_id]
    assert replay.metadata['decision']['resolution'] == 'replay_completed'
    customer = registry.find_by_identity(tenant_id='t1', business_id='b1', channel='telegram', external_subject='42')
    assert customer.customer.customer_id == customer_id
    assert customer.identities[0].last_contact_at_ms is not None
    timeline = CustomerTimelineProjector(events).get(tenant_id='t1', business_id='b1', customer_id=customer_id)
    assert [entry.kind for entry in timeline.entries] == ['customer.created', 'customer.identity.attached', 'customer.contact.observed']


def test_invalid_signature_never_projects_customer(monkeypatch):
    from crm import CustomerRegistry
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: False)
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = CustomerRegistry(event_store=events, idempotency_store=claims, pii_vault=InMemorySecretVault())
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(claims),
        customer_registry=registry,
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-invalid', topic='telegram_update', owner_id='provider_admin')
    assert out.status == 'invalid_signature'
    assert list(events.iter_events(tenant_id='t1', start_ms=0)) == []


class _VkAckResponder:
    def __init__(self, *, ok: bool = True) -> None:
        self.calls = []
        self.ok = ok

    def acknowledge(self, **kwargs):
        self.calls.append(kwargs)
        return {
            'required': True,
            'ok': self.ok,
            'kind': 'vk_message_event_answer',
            **({} if self.ok else {'reason': 'provider_rejected'}),
        }


def test_vk_message_event_is_acknowledged_after_processing_and_on_completed_replay(monkeypatch):
    provider = provider_map()['vk_messaging']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    processor = _Processor()
    responder = _VkAckResponder()
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=processor,
        operational_responder=responder,
    )
    body = b'{"type":"message_event","group_id":123,"object":{"event_id":"evt-vk","user_id":42,"peer_id":42,"payload":{"callback_data":"menu:open"}}}'
    first = service.ingest(
        provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body,
        event_key='evt-vk', topic='message_event', owner_id='provider_admin',
    )
    replay = service.ingest(
        provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body,
        event_key='evt-vk', topic='message_event', owner_id='provider_admin',
    )
    assert first.metadata['provider_ack']['ok'] is True
    assert replay.metadata['decision']['resolution'] == 'replay_completed'
    assert replay.metadata['provider_ack']['ok'] is True
    assert service.transport_ack_safe(first) is True
    assert service.transport_ack_safe(replay) is True
    assert processor.calls == 1
    assert len(responder.calls) == 2


def test_vk_message_event_ack_failure_keeps_http_transport_fail_closed(monkeypatch):
    provider = provider_map()['vk_messaging']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=_Processor(),
        operational_responder=_VkAckResponder(ok=False),
    )
    body = b'{"type":"message_event","group_id":123,"object":{"event_id":"evt-vk-fail","user_id":42,"peer_id":42,"payload":{"callback_data":"menu:open"}}}'
    out = service.ingest(
        provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body,
        event_key='evt-vk-fail', topic='message_event', owner_id='provider_admin',
    )
    assert out.metadata['provider_ack']['required'] is True
    assert out.metadata['provider_ack']['ok'] is False
    assert service.transport_ack_safe(out) is False
