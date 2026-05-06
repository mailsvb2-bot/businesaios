from runtime.effects.message_effects import send_message_effect


class _DummyEventLog:
    def __init__(self):
        self.items = []

    def emit(self, **kwargs):
        self.items.append(kwargs)


class _DummySelf:
    def __init__(self):
        self.event_log = _DummyEventLog()
        self.telegram_outbound_queue = None
        self.delivery_state = None
        self._last_sent = {}

    def _telegram_send_message(self, **kwargs):
        return True, {"channel": "telegram", "sent": True}

    def _telegram_answer_callback(self, *args, **kwargs):
        return True

    def _telegram_send_chat_action(self, *args, **kwargs):
        return True


def test_non_telegram_send_uses_multichannel_bridge(monkeypatch):
    import runtime.effects.message_effects as mod
    from runtime.messaging.delivery_result import DeliveryResult

    class _Bridge:
        def send(self, msg):
            return DeliveryResult(ok=True, channel=msg.channel, mode="webhook", external_id="wa-ext-1", detail={"provider": "whatsapp"})

    telegram_mod = mod._telegram_messaging_module()
    monkeypatch.setattr("runtime._internal.effects_actions.telegram.messaging_parts.transport.get_multichannel_effects_bridge", lambda: _Bridge())
    dummy = _DummySelf()
    out = send_message_effect(dummy, decision_id="d1", correlation_id="c1", user_id="wa:100", text="hello", channel="whatsapp", track_payload={"tenant_id": "tenant-x"})
    assert out["ok"] is True
    assert out["meta"]["provider"] == "whatsapp"
    assert out["meta"]["mode"] == "webhook"


def test_telegram_send_stays_in_telegram_transport():
    dummy = _DummySelf()
    out = send_message_effect(dummy, decision_id="d1", correlation_id="c1", user_id="123456", text="hello", channel="telegram")
    assert out["ok"] is True
    assert out["meta"]["channel"] == "telegram"
