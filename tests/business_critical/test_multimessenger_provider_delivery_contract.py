from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from interfaces.messaging._shared import outbound_sender
from interfaces.messaging._shared.delivery_mapper import map_delivery_result
from interfaces.messaging._shared.provider_config import ProviderConfig
from runtime._internal.effects_actions.telegram import messaging as messaging_effect
from runtime._internal.effects_actions.telegram.delivery_evidence import (
    build_delivery_evidence,
)
from runtime._internal.effects_actions.telegram.messaging_parts import (
    transport as delivery_transport,
)
from runtime.messaging import CHANNEL_SPECS
from runtime.messaging.bootstrap import build_multichannel_dispatcher
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


WEBHOOK_CHANNELS = tuple(
    channel
    for channel, spec in CHANNEL_SPECS.items()
    if spec.mode_default == "webhook"
)


class FakeHTTPResponse:
    def __init__(
        self,
        *,
        status: int,
        payload: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        self.status = status
        self._raw = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else b""
        )
        self.headers = dict(headers or {})

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self) -> int:
        return self.status

    def read(self, limit: int = -1) -> bytes:
        return self._raw if limit < 0 else self._raw[:limit]


def _message(*, channel: str, user_id: str = "recipient-1") -> OutboundMessage:
    return OutboundMessage(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        user_id=user_id,
        channel=channel,
        text="Canonical message",
        payload={
            "text": "Canonical message",
            "execution_entrypoint": "runtime.execution.decision_execution_service",
        },
    )


@pytest.mark.lock
def test_webhook_delivery_requires_a_real_provider_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_urlopen(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHTTPResponse(
            status=202,
            payload={
                "status": "accepted",
                "messages": [{"id": "wamid.provider-1"}],
            },
        )

    monkeypatch.setattr(outbound_sender.urllib_request, "urlopen", fake_urlopen)
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")

    cfg = ProviderConfig(
        provider="whatsapp",
        env_prefix="WHATSAPP",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-number",
        token_present=False,
    )
    msg = _message(channel="whatsapp")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    sent_payload = json.loads(captured["request"].data.decode("utf-8"))
    assert sent_payload["tenant_id"] == "business-a"
    assert sent_payload["recipient"] == "recipient-1"
    assert sent_payload["delivery_key"] == msg.delivery_key
    assert captured["request"].get_header("Idempotency-key") == msg.delivery_key
    assert captured["timeout"] == 8.0
    assert raw["accepted"] is True
    assert raw["delivered"] is False
    assert result.ok is True
    assert result.mode == "accepted"
    assert result.external_id == "wamid.provider-1"
    assert result.external_id != msg.delivery_key


@pytest.mark.lock
@pytest.mark.parametrize("channel", WEBHOOK_CHANNELS)
def test_every_webhook_channel_requires_and_preserves_provider_receipt(
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
) -> None:
    spec = CHANNEL_SPECS[channel]
    receipt = f"{channel}-provider-receipt"
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=202,
            payload={"status": "accepted", "message_id": receipt},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")

    cfg = ProviderConfig(
        provider=channel,
        env_prefix=spec.provider_env_prefix,
        mode=spec.mode_default,
        endpoint="https://gateway.example.test/messages",
        sender="business-sender",
        token_present=False,
    )
    msg = _message(channel=channel)

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["provider"] == channel
    assert raw["accepted"] is True
    assert raw["delivered"] is False
    assert result.ok is True
    assert result.external_id == receipt
    assert result.external_id != msg.delivery_key


@pytest.mark.lock
@pytest.mark.parametrize("channel", WEBHOOK_CHANNELS)
def test_every_webhook_dispatch_adapter_reaches_receipt_backed_transport(
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
) -> None:
    spec = CHANNEL_SPECS[channel]
    receipt = f"{channel}-dispatcher-receipt"
    monkeypatch.setenv(f"{spec.provider_env_prefix}_MODE", "webhook")
    monkeypatch.setenv(
        f"{spec.provider_env_prefix}_ENDPOINT",
        "https://gateway.example.test/messages",
    )
    monkeypatch.setenv(f"{spec.provider_env_prefix}_SENDER", "business-sender")
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=202,
            payload={"status": "accepted", "message_id": receipt},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)

    result = build_multichannel_dispatcher().send(_message(channel=channel))

    assert result.ok is True
    assert result.channel == channel
    assert result.mode == "accepted"
    assert result.external_id == receipt


@pytest.mark.lock
@pytest.mark.parametrize("channel", ["web_chat", "api"])
def test_disabled_safe_internal_adapter_never_reports_delivery_success(
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
) -> None:
    spec = CHANNEL_SPECS[channel]
    monkeypatch.setenv(
        f"{spec.provider_env_prefix}_MODE",
        "configured_noop",
    )

    result = build_multichannel_dispatcher().send(_message(channel=channel))

    assert result.ok is False
    assert result.mode == "configured_noop"
    assert result.external_id == ""


@pytest.mark.lock
def test_webhook_2xx_without_provider_receipt_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=200,
            payload={"ok": True},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")

    cfg = ProviderConfig(
        provider="viber",
        env_prefix="VIBER",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-a",
        token_present=False,
    )
    msg = _message(channel="viber")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["ok"] is False
    assert raw["reason"] == "provider_receipt_missing"
    assert result.ok is False
    assert result.external_id == ""


@pytest.mark.lock
def test_webhook_rejects_a_locally_echoed_delivery_key_as_provider_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = _message(channel="slack")
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=202,
            payload={"status": "accepted", "message_id": msg.delivery_key},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")
    cfg = ProviderConfig(
        provider="slack",
        env_prefix="SLACK",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-sender",
        token_present=False,
    )

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["ok"] is False
    assert raw["reason"] == "provider_receipt_not_external"
    assert result.ok is False
    assert result.external_id == ""


@pytest.mark.lock
@pytest.mark.parametrize(
    "provider_payload",
    [
        {"ok": False, "status": "accepted", "message_id": "receipt-1"},
        {"success": False, "status": "accepted", "message_id": "receipt-2"},
        {"status": "failed", "message_id": "receipt-3"},
        {"status": "accepted", "message_id": "receipt-4", "error": "quota"},
    ],
)
def test_provider_declared_rejection_overrides_http_2xx_and_receipt(
    monkeypatch: pytest.MonkeyPatch,
    provider_payload: dict,
) -> None:
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=200,
            payload=provider_payload,
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")
    cfg = ProviderConfig(
        provider="discord",
        env_prefix="DISCORD",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-sender",
        token_present=False,
    )
    msg = _message(channel="discord")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["ok"] is False
    assert raw["reason"] == "provider_rejected_message"
    assert result.ok is False


@pytest.mark.lock
@pytest.mark.parametrize("status", ["sent", "success", "succeeded"])
def test_nonfinal_provider_status_is_acceptance_not_fabricated_delivery(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=200,
            payload={"status": status, "message_id": f"receipt-{status}"},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")
    cfg = ProviderConfig(
        provider="whatsapp",
        env_prefix="WHATSAPP",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-sender",
        token_present=False,
    )
    msg = _message(channel="whatsapp")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["accepted"] is True
    assert raw["delivered"] is False
    assert result.ok is True
    assert result.mode == "accepted"


@pytest.mark.lock
@pytest.mark.parametrize("status", ["delivered", "read"])
def test_explicit_final_provider_status_remains_verified_delivery(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    monkeypatch.setattr(
        outbound_sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: FakeHTTPResponse(
            status=200,
            payload={"status": status, "message_id": f"receipt-{status}"},
        ),
    )
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 8.0)
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")
    cfg = ProviderConfig(
        provider="messenger",
        env_prefix="MESSENGER",
        mode="webhook",
        endpoint="https://gateway.example.test/messages",
        sender="business-sender",
        token_present=False,
    )
    msg = _message(channel="messenger")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["accepted"] is True
    assert raw["delivered"] is True
    assert result.ok is True
    assert result.mode == "webhook"
    assert result.detail["delivered"] is True


@pytest.mark.lock
@pytest.mark.parametrize(
    "raw, expected_reason",
    [
        (
            {
                "ok": False,
                "accepted": True,
                "delivered": False,
                "external_id": "provider-receipt",
            },
            "provider_result_contradictory",
        ),
        (
            {
                "ok": True,
                "accepted": True,
                "delivered": False,
                "external_id": "__delivery_key__",
            },
            "provider_receipt_not_external",
        ),
    ],
)
def test_delivery_mapper_rejects_contradictory_or_local_success(
    raw: dict,
    expected_reason: str,
) -> None:
    msg = _message(channel="viber")
    payload = dict(raw)
    if payload["external_id"] == "__delivery_key__":
        payload["external_id"] = msg.delivery_key

    result = map_delivery_result(msg=msg, raw=payload)

    assert result.ok is False
    assert result.external_id == ""
    assert result.detail["reason"] == expected_reason


@pytest.mark.lock
def test_configured_noop_can_never_be_delivery_success() -> None:
    cfg = ProviderConfig(
        provider="web_chat",
        env_prefix="WEB_CHAT",
        mode="configured_noop",
        endpoint="",
        sender="",
        token_present=False,
    )
    msg = _message(channel="web_chat")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["ok"] is False
    assert raw["accepted"] is False
    assert raw["delivered"] is False
    assert result.ok is False
    assert result.external_id == ""


@pytest.mark.lock
def test_malformed_smtp_endpoint_fails_closed_without_transport_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        outbound_sender.smtplib,
        "SMTP",
        lambda *_args, **_kwargs: pytest.fail("SMTP must not be called"),
    )
    monkeypatch.setattr(outbound_sender, "env_str", lambda *_args, **_kwargs: "")
    cfg = ProviderConfig(
        provider="email",
        env_prefix="EMAIL",
        mode="smtp",
        endpoint="smtp://smtp.example.test:not-a-port",
        sender="sender@example.test",
        token_present=False,
    )
    msg = _message(channel="email", user_id="owner@example.test")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert raw["ok"] is False
    assert raw["reason"] == "smtp_coordinates_missing"
    assert result.ok is False


@pytest.mark.lock
@pytest.mark.parametrize(
    "channel, expected_action_type",
    [
        ("telegram", "telegram.send_message"),
        ("slack", "messaging.send_message"),
        ("discord", "messaging.send_message"),
    ],
)
def test_delivery_evidence_never_mislabels_nontelegram_as_telegram(
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
    expected_action_type: str,
) -> None:
    captured = {}
    msg = SimpleNamespace(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        user_id="owner-1",
        channel=channel,
        text="Canonical message",
        track_event_type=None,
        track_payload=None,
    )

    monkeypatch.setattr(
        messaging_effect,
        "build_outbound_message",
        lambda **_kwargs: msg,
    )
    monkeypatch.setattr(
        messaging_effect,
        "build_single_sender",
        lambda _effects: object(),
    )
    monkeypatch.setattr(
        messaging_effect,
        "execute_delivery_path",
        lambda *_args, **_kwargs: (
            True,
            {
                "channel": channel,
                "external_id": "provider-receipt-1",
                "delivery_finalized": True,
            },
        ),
    )
    monkeypatch.setattr(messaging_effect, "track_delivery", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(messaging_effect, "track_business_event", lambda *_args, **_kwargs: None)

    def fake_evidence(*, ok, meta, action_type):
        captured.update(
            {
                "ok": ok,
                "meta": dict(meta),
                "action_type": action_type,
            }
        )
        return {"verified": True, "action_type": action_type}

    monkeypatch.setattr(
        messaging_effect,
        "build_delivery_evidence",
        fake_evidence,
    )

    result = messaging_effect.send_message_effect(
        object(),
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        user_id="owner-1",
        text="Canonical message",
        channel=channel,
    )

    assert result["ok"] is True
    assert captured["action_type"] == expected_action_type


@pytest.mark.lock
def test_smtp_success_means_server_acceptance_not_fabricated_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, *, timeout):
            sent["coordinates"] = (host, port, timeout)

        def ehlo(self):
            sent["ehlo"] = sent.get("ehlo", 0) + 1

        def starttls(self):
            raise AssertionError("STARTTLS disabled by test")

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["message"] = message
            return {}

        def quit(self):
            sent["quit"] = True

    values = {
        "EMAIL_USERNAME": "mailer",
        "EMAIL_PASSWORD": "secret",
    }
    monkeypatch.setattr(outbound_sender.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(outbound_sender, "env_bool", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(outbound_sender, "env_float", lambda *_args, **_kwargs: 6.0)
    monkeypatch.setattr(
        outbound_sender,
        "env_str",
        lambda name, default="": values.get(name, default),
    )

    cfg = ProviderConfig(
        provider="email",
        env_prefix="EMAIL",
        mode="smtp",
        endpoint="smtp://smtp.example.test:2525",
        sender="sender@example.test",
        token_present=True,
    )
    msg = _message(channel="email", user_id="owner@example.test")

    raw = outbound_sender.send_outbound(cfg=cfg, msg=msg)
    result = map_delivery_result(msg=msg, raw=raw)

    assert sent["coordinates"] == ("smtp.example.test", 2525, 6.0)
    assert sent["login"] == ("mailer", "secret")
    assert sent["message"]["To"] == "owner@example.test"
    assert sent["quit"] is True
    assert raw["accepted"] is True
    assert raw["delivered"] is False
    assert result.ok is True
    assert result.mode == "accepted"
    assert result.external_id == sent["message"]["Message-ID"]


@pytest.mark.lock
def test_nontelegram_provider_acceptance_is_persisted_and_retry_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDeliveryState:
        def __init__(self) -> None:
            self.receipts: dict[str, dict] = {}

        def get_receipt(self, delivery_key: str):
            return self.receipts.get(delivery_key)

        def mark_accepted(self, delivery_key: str, *, payload_digest, metadata):
            self.receipts[delivery_key] = {
                "delivery_phase": "accepted_for_delivery",
                "payload_digest": payload_digest,
                "metadata": dict(metadata),
            }

    class FakeBridge:
        def __init__(self) -> None:
            self.calls: list[OutboundMessage] = []

        def send(self, msg: OutboundMessage) -> DeliveryResult:
            self.calls.append(msg)
            return DeliveryResult(
                ok=True,
                channel=msg.channel,
                mode="accepted",
                external_id="provider-receipt-1",
                detail={
                    "accepted": True,
                    "tenant_id": "forged-tenant",
                    "user_id": "forged-user",
                    "decision_id": "forged-decision",
                    "correlation_id": "forged-correlation",
                    "payload_digest": "forged-digest",
                },
            )

    state = FakeDeliveryState()
    bridge = FakeBridge()
    effects = SimpleNamespace(delivery_state=state)
    msg = _message(channel="line")
    monkeypatch.setattr(
        delivery_transport,
        "get_multichannel_effects_bridge",
        lambda: bridge,
    )

    first_ok, first_meta = delivery_transport.multichannel_delivery(effects, msg=msg)
    second_ok, second_meta = delivery_transport.multichannel_delivery(effects, msg=msg)

    assert first_ok is True
    assert first_meta["delivery_phase"] == "accepted_for_delivery"
    assert second_ok is True
    assert second_meta["dedup"] is True
    assert len(bridge.calls) == 1
    stored = state.receipts[msg.delivery_key]
    assert stored["payload_digest"] == msg.payload_digest
    assert stored["metadata"]["tenant_id"] == "business-a"
    assert stored["metadata"]["user_id"] == "recipient-1"
    assert stored["metadata"]["decision_id"] == "decision-1"
    assert stored["metadata"]["correlation_id"] == "correlation-1"
    assert stored["metadata"]["payload_digest"] == msg.payload_digest

    evidence = build_delivery_evidence(
        ok=second_ok,
        meta=second_meta,
        action_type="messaging.send_message",
    )
    assert evidence["verified"] is True
    assert evidence["status"] == "observed"
    assert evidence["external_refs"] == [
        "provider-receipt-1",
        msg.delivery_key,
    ]
