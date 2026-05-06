from runtime.messaging.outbound_message import OutboundMessage


def test_delivery_key_changes_when_reply_markup_changes() -> None:
    a = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hi', reply_markup={'inline_keyboard': [[{'text': 'A'}]]})
    b = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hi', reply_markup={'inline_keyboard': [[{'text': 'B'}]]})
    assert a.delivery_key != b.delivery_key
