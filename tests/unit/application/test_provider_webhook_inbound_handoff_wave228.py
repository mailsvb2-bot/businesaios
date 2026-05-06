from runtime.business_autonomy.provider_webhook_inbound_handoff import build_provider_webhook_inbound_handoff


def test_build_provider_webhook_inbound_handoff_creates_canonical_message_and_world_state_input():
    out = build_provider_webhook_inbound_handoff(
        tenant_id='t1',
        business_id='b1',
        provider_key='telegram_bot',
        messaging_ingress={
            'channel': 'telegram',
            'user_id': '42',
            'text': 'hello',
            'transport_message_id': 'm1',
            'correlation_id': 'c1',
        },
        route_metadata={'event_key': 'e1'},
    )
    assert out['inbound_message']['channel'] == 'telegram'
    assert out['inbound_message']['user_id'] == '42'
    assert out['world_state_input']['message_text'] == 'hello'
    assert out['ingress_owner'] == 'runtime.messaging.inbound_entrypoint'
