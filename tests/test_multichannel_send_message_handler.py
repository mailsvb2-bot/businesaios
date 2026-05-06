from runtime.handlers_messaging import handle_send_message


class _Effects:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, "channel": kwargs["channel"]}


class _Decision:
    decision_id = "d-1"
    correlation_id = "c-1"


class _Env:
    decision = _Decision()



def test_handle_send_message_passes_channel_through():
    fx = _Effects()
    out = handle_send_message({"user_id": "wa:1", "text": "hello", "channel": "whatsapp"}, fx, _Env())
    assert out["ok"] is True
    assert fx.calls[0]["channel"] == "whatsapp"
