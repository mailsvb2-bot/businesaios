import asyncio
import pytest

from interfaces.messaging_runtime.bootstrap import build_multichannel_runtime_app
from interfaces.messaging_runtime.channel_factory import TransportSendNotConfigured
from interfaces.messaging_runtime.state.guards import InboundDuplicateDetected


def build_world_state(payload):
    return {"reply_text": f"reply:{payload.message_text}"}


async def send_ok(outbound):
    return {"status": "sent", "channel": outbound.channel, "body": outbound.body}


def test_runtime_app_has_single_enabled_flow():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_ok},
        raw_config={
            "channels": {
                "sms": {"provider": "twilio", "enabled": True, "retry_max_attempts": 2, "backpressure_limit": 10},
            },
            "defaults": {"queue_limit": 10, "max_attempts": 2},
        },
    )
    outbound = app.accept_inbound(
        "sms",
        {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"},
    )
    assert outbound.body == "reply:hello"
    assert app.queue_service.size() == 1


def test_duplicate_inbound_is_blocked():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_ok},
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {}},
    )
    app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    with pytest.raises(InboundDuplicateDetected):
        app.accept_inbound("sms", {"user_id": "u1", "text": "hello2", "message_id": "m1", "correlation_id": "c2"})


def test_missing_sender_is_explicit_not_fake_success():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {}},
    )
    app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    with pytest.raises(TransportSendNotConfigured):
        asyncio.run(app.dispatcher.dispatch_once())
