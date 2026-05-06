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
