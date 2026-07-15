from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from interfaces.messaging._shared import outbound_sender
from interfaces.messaging._shared.delivery_mapper import map_delivery_result
from interfaces.messaging._shared.provider_config import ProviderConfig
from runtime._internal.effects_actions.telegram import messaging as messaging_effect
from runtime.messaging.outbound_message import OutboundMessage


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
