from __future__ import annotations

import pytest

import runtime._internal.effects_actions.telegram.media as media_effect
from application.business_autonomy.provider_catalog import provider_map
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.outbound_message import OutboundMessage


class _EventLog:
    def __init__(self) -> None:
        self.events = []

    def emit(self, **kwargs):
        self.events.append(kwargs)


class _Effects:
    def __init__(self) -> None:
        self.event_log = _EventLog()
        self.delivery_state = None
        self._audio_lock = None
        self._last_audio_sent_at = None
        self._audio_delivery_keys = None
        self._min_audio_interval_s = 0.0


@pytest.mark.parametrize("channel", ["vk", "max"])
def test_send_audio_effect_builds_canonical_multimessenger_attachment(monkeypatch, channel: str) -> None:
    effects = _Effects()
    captured = {}
    monkeypatch.setattr(media_effect, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(media_effect, "assert_event_log_tenant", lambda *_args, **_kwargs: "tenant-a")
    monkeypatch.setattr(media_effect, "current_execution_business_id", lambda: "business-a")
    monkeypatch.setattr(media_effect, "build_single_sender", lambda _effects: object())

    def fake_delivery(_effects, *, msg, channel_policy, send_once):
        captured["msg"] = msg
        captured["channel_policy"] = channel_policy
        captured["send_once"] = send_once
        return True, {"mode": "accepted", "delivery_phase": "accepted_for_delivery", "delivery_finalized": False}

    monkeypatch.setattr(media_effect, "execute_delivery_path", fake_delivery)
    result = media_effect.send_audio_effect(
        effects,
        decision_id="decision-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        business_id="business-a",
        user_id="77",
        path="/private/audio.ogg",
        kind="voice",
        caption="listen",
        channel=channel,
    )
    msg = captured["msg"]
    assert msg.channel == channel
    assert msg.business_id == "business-a"
    assert msg.attachments == ({"kind": "voice", "source": "/private/audio.ogg"},)
    assert msg.text == "listen"
    assert result["ok"] is True
    assert result["evidence"]["action_type"] == "messaging.send_audio"


def test_send_audio_native_channel_requires_business_scope(monkeypatch) -> None:
    effects = _Effects()
    monkeypatch.setattr(media_effect, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(media_effect, "assert_event_log_tenant", lambda *_args, **_kwargs: "tenant-a")
    monkeypatch.setattr(media_effect, "current_execution_business_id", lambda: "")

    result = media_effect.send_audio_effect(
        effects,
        decision_id="decision-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        user_id="77",
        path="/private/audio.ogg",
        channel="max",
    )
    assert result["ok"] is False
    assert result["meta"]["error"] == "NATIVE_BUSINESS_ID_REQUIRED"


@pytest.mark.parametrize("channel,provider_key", [("vk", "vk_messaging"), ("max", "max_messaging")])
def test_native_provider_adapter_forwards_audio_through_existing_approval_queue(channel: str, provider_key: str) -> None:
    class _Registry:
        def get(self, key):
            return provider_map()[key]

    class _Service:
        provider_registry = _Registry()

        def __init__(self):
            self.calls = []

        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "dispatch": {
                    "queued": False,
                    "status": "rejected_provider_write_guard",
                    "job_id": "",
                    "metadata": {
                        "provider_write_guard": {
                            "reason": "approval_required",
                            "metadata": {"approval": {"approval_id": "approval-1", "approval_required": True}},
                        }
                    },
                },
                "result": None,
            }
    service = _Service()
    adapter = _NativeProviderQueueAdapter(channel, service_factory=lambda: service)
    msg = OutboundMessage(
        decision_id="decision-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        business_id="business-a",
        user_id="77",
        channel=channel,
        text="listen",
        attachments=({"kind": "voice", "source": "/private/audio.ogg"},),
        track_payload={"_provider_native": {"business_id": "business-a"}},
    )

    result = adapter.send(msg)

    assert result.ok is False and result.mode == "approval_required"
    sent = service.calls[0]
    assert sent["provider_key"] == provider_key
    assert sent["operation"] == "message_send"
    assert sent["payload"]["attachments"] == [{"kind": "voice", "source": "/private/audio.ogg"}]
    assert sent["payload"]["_approval"]["decision_id"] == "decision-1"
