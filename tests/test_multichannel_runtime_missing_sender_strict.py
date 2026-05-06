import asyncio
import pytest

from interfaces.messaging_runtime.bootstrap import build_multichannel_runtime_app
from interfaces.messaging_runtime.channel_factory import TransportSendNotConfigured


def build_world_state(payload):
    return {"reply_text": f"reply:{payload.message_text}"}


def test_missing_sender_raises_not_dead_letters() -> None:
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {}},
    )
    outbound = app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    with pytest.raises(TransportSendNotConfigured):
        asyncio.run(app.dispatcher.dispatch_once())
    state = app.attempt_store.get(outbound.dedupe_key)
    assert state is not None
    assert state.status == "transport_not_configured"
    assert app.dead_letter_store.size() == 0
