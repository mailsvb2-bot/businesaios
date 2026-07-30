from interfaces.messaging.email import Runner as EmailRunner
from interfaces.messaging.whatsapp import Runner as WhatsAppRunner
from interfaces.web.chat_widget.runner import Runner as WebChatRunner
from runtime.messaging.outbound_message import OutboundMessage


def _message(*, channel: str, user_id: str) -> OutboundMessage:
    return OutboundMessage(
        decision_id="d1",
        correlation_id="c1",
        tenant_id="t1",
        user_id=user_id,
        channel=channel,
        text="hello",
    )


def test_whatsapp_runner_fails_closed_without_provider_endpoint(monkeypatch):
    monkeypatch.delenv("WHATSAPP_ENDPOINT", raising=False)
    monkeypatch.delenv("WHATSAPP_MODE", raising=False)

    result = WhatsAppRunner().send(
        _message(channel="whatsapp", user_id="wa:1")
    )

    assert result.channel == "whatsapp"
    assert result.ok is False
    assert result.mode == "failed"
    assert result.error == "provider_endpoint_missing_or_invalid"


def test_email_runner_fails_closed_without_smtp_coordinates(monkeypatch):
    for key in (
        "EMAIL_ENDPOINT",
        "EMAIL_SENDER",
        "EMAIL_USERNAME",
        "EMAIL_PASSWORD",
        "EMAIL_TOKEN",
        "EMAIL_MODE",
    ):
        monkeypatch.delenv(key, raising=False)

    result = EmailRunner().send(
        _message(channel="email", user_id="user@example.com")
    )

    assert result.channel == "email"
    assert result.ok is False
    assert result.mode == "failed"
    assert result.error == "smtp_coordinates_missing"


def test_webchat_runner_returns_explicit_unsent_noop():
    result = WebChatRunner().send(
        _message(channel="web_chat", user_id="session-1")
    )

    assert result.channel == "web_chat"
    assert result.ok is False
    assert result.mode == "configured_noop"
    assert result.error == "provider_not_enabled"
