import asyncio

from interfaces.messaging_runtime.bootstrap import build_multichannel_runtime_app


def build_world_state(payload):
    return {"reply_text": f"reply:{payload.message_text}"}


async def send_ok(outbound):
    return {"status": "sent", "channel": outbound.channel}


async def send_fail(outbound):
    raise RuntimeError("permanent failure")


def test_delivery_success_and_ack_reconciliation():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_ok},
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {"max_attempts": 2}},
    )
    outbound = app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    result = asyncio.run(app.dispatcher.dispatch_once())
    assert result["status"] == "sent"
    ack = app.ack_reconciliation.reconcile(
        provider_message_id="provider-1",
        dedupe_key=outbound.dedupe_key,
        channel="sms",
        status="acknowledged",
    )
    assert ack["status"] == "ack_recorded"
    assert app.attempt_store.get(outbound.dedupe_key).status == "acknowledged"


def test_dead_letter_on_permanent_failure():
    app = build_multichannel_runtime_app(
        build_world_state=build_world_state,
        senders={"sms": send_fail},
        raw_config={"channels": {"sms": {"provider": "twilio"}}, "defaults": {"max_attempts": 1}},
    )
    app.accept_inbound("sms", {"user_id": "u1", "text": "hello", "message_id": "m1", "correlation_id": "c1"})
    result = asyncio.run(app.dispatcher.dispatch_once())
    assert result["status"] == "dead_letter"
    assert app.dead_letter_store.size() == 1
