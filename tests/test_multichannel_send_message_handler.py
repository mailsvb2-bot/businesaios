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


def test_handle_vk_message_binds_native_provider_context():
    fx = _Effects()
    handle_send_message({"tenant_id": "tenant-a", "business_id": "biz-a", "approval_id": "ap-1", "user_id": "42", "text": "hello", "channel": "vk"}, fx, _Env())
    assert fx.calls[0]["track_payload"]["_provider_native"] == {"business_id": "biz-a", "approval_id": "ap-1"}


def test_handle_slack_discord_messages_bind_native_queue_context():
    for channel, channel_id in (("slack", "C123"), ("discord", "123")):
        fx = _Effects()
        handle_send_message({"tenant_id": "tenant-a", "business_id": "biz-a", "channel_id": channel_id, "user_id": "user-1", "text": "hello", "channel": channel}, fx, _Env())
        assert fx.calls[0]["track_payload"]["_provider_native"] == {"business_id": "biz-a", "channel_id": channel_id}
