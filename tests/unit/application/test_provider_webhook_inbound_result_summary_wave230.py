from runtime.business_autonomy.provider_webhook_inbound_result_summary import summarize_provider_webhook_inbound_result


def test_summarize_provider_webhook_inbound_result_returns_canonical_summary():
    out = summarize_provider_webhook_inbound_result(
        handoff={
            'inbound_message': {
                'channel': 'telegram',
                'user_id': 'u1',
                'correlation_id': 'c1',
                'transport_message_id': 'm1',
            }
        },
        inbound_result={
            'accepted': True,
            'decision_envelope': {'decision_id': 'd1'},
        },
    )

    assert out == {
        'accepted': True,
        'decision_id': 'd1',
        'channel': 'telegram',
        'user_id': 'u1',
        'correlation_id': 'c1',
        'transport_message_id': 'm1',
    }
