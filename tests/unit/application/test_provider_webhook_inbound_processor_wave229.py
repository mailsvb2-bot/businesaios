from runtime.business_autonomy.provider_webhook_inbound_processor import ProviderWebhookInboundProcessor


class _Core:
    pass


def test_provider_webhook_inbound_processor_issues_canonical_message_decision(monkeypatch):
    calls = {}

    class _Gateway:
        def __init__(self, *, decision_core, caller: str):
            calls['caller'] = caller
            calls['decision_core'] = decision_core

        def issue(self, *, message):
            calls['message'] = message
            return {'decision_id': 'd1'}

    monkeypatch.setattr('runtime.business_autonomy.provider_webhook_inbound_processor.MessagingInboundDecisionGateway', _Gateway)

    processor = ProviderWebhookInboundProcessor(decision_core=_Core())
    out = processor.process(
        handoff={
            'inbound_message': {
                'tenant_id': 't1',
                'channel': 'telegram',
                'user_id': 'u1',
                'text': 'hello',
                'correlation_id': 'c1',
                'transport_message_id': 'm1',
                'metadata': {'provider_key': 'telegram_bot'},
            }
        }
    )

    assert out['accepted'] is True
    assert out['decision_envelope']['decision_id'] == 'd1'
    assert calls['caller'] == 'runtime.business_autonomy.provider_webhook_inbound_processor'
    assert calls['message'].channel == 'telegram'


def test_provider_webhook_inbound_processor_rejects_missing_and_failed_gateway_decisions(monkeypatch):
    for envelope in (None, False, {}, {'accepted': False}, {'ok': False}):
        class _Gateway:
            def __init__(self, *, decision_core, caller):
                pass

            def process(self, *, message):
                return envelope

        monkeypatch.setattr(
            'runtime.business_autonomy.provider_webhook_inbound_processor.MessagingInboundDecisionGateway',
            _Gateway,
        )
        result = ProviderWebhookInboundProcessor(decision_core=_Core()).process(
            handoff={
                'inbound_message': {
                    'tenant_id': 't1', 'channel': 'telegram',
                    'user_id': 'u1', 'text': 'hello',
                    'correlation_id': 'c1', 'transport_message_id': 'm1',
                },
            },
        )
        assert result['accepted'] is False
        assert result['decision_envelope'] == envelope


def test_inbound_processor_rejects_invalid_identity_before_decision_core(monkeypatch):
    calls = []

    class _Gateway:
        def __init__(self, **kwargs):
            calls.append('constructed')

    monkeypatch.setattr(
        'runtime.business_autonomy.provider_webhook_inbound_processor.MessagingInboundDecisionGateway',
        _Gateway,
    )
    valid = {'tenant_id': 't1', 'channel': 'telegram', 'user_id': 'u1', 'text': 'hello'}
    for key, value in (
        ('tenant_id', ' '), ('channel', ''), ('user_id', None),
        ('text', []), ('text', '   '),
    ):
        malformed = {**valid, key: value}
        out = ProviderWebhookInboundProcessor(decision_core=_Core()).process(
            handoff={'inbound_message': malformed},
        )
        assert out == {'accepted': False, 'reason': 'invalid_inbound_identity_or_text'}
    assert calls == []


def test_inbound_processor_retains_trusted_source_and_chat_metadata(monkeypatch):
    captured = {}

    class _Gateway:
        def __init__(self, **kwargs):
            pass

        def process(self, *, message):
            captured['metadata'] = message.metadata
            return {'decision_id': 'd1'}

    monkeypatch.setattr(
        'runtime.business_autonomy.provider_webhook_inbound_processor.MessagingInboundDecisionGateway',
        _Gateway,
    )
    out = ProviderWebhookInboundProcessor(decision_core=_Core()).process(
        handoff={'inbound_message': {
            'tenant_id': 't1', 'channel': 'telegram', 'user_id': 'u1',
            'text': 'hello', 'chat_id': 'real-chat',
            'metadata': {'source': 'spoofed', 'chat_id': 'spoofed-chat', 'customer_id': 'c1'},
        }},
    )
    assert out['accepted'] is True
    assert captured['metadata']['source'] == 'provider_webhook_handoff'
    assert captured['metadata']['chat_id'] == 'real-chat'
    assert captured['metadata']['customer_id'] == 'c1'
