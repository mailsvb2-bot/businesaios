from interfaces.messaging_runtime.bootstrap import build_multichannel_runtime_app
from interfaces.messaging_runtime.config import load_runtime_config


def build_world_state(payload):
    return {"reply_text": f"reply:{payload.message_text}"}


async def send_ok(outbound):
    return {"status": "sent", "channel": outbound.channel}


def test_config_filters_enabled_channels():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_ok},
        raw_config={
            "channels": {
                "sms": {"provider": "twilio", "enabled": True},
                "email": {"provider": "mailgun", "enabled": False},
            }
        },
    )
    assert tuple(sorted(app.registry.channels())) == ("sms",)


def test_audit_and_anomaly_hooks_receive_events():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_ok},
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {}},
    )
    app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    records = app.audit_trail.snapshot()
    names = [item.event_name for item in records]
    assert "route_built" in names
    assert "worldstate_built" in names
    assert "outbound_enqueued" in names


def test_runtime_config_loader_merges_defaults():
    config = load_runtime_config(
        {"channels": {"sms": {"provider": "twilio"}}, "defaults": {"max_attempts": 7}}
    )
    assert config.defaults["queue_limit"] == 1000
    assert config.defaults["max_attempts"] == 7
