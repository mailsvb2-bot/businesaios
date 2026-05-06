from interfaces.messaging.whatsapp import Runner as WhatsAppRunner
from interfaces.messaging.email import Runner as EmailRunner
from interfaces.web.chat_widget.runner import Runner as WebChatRunner
from runtime.messaging.outbound_message import OutboundMessage


def test_whatsapp_runner_returns_delivery_result():
    runner = WhatsAppRunner()
    out = runner.send(OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="wa:1", channel="whatsapp", text="hello"))
    assert out.channel == "whatsapp"
    assert out.mode in {"webhook", "configured_noop"}


def test_email_runner_returns_delivery_result():
    runner = EmailRunner()
    out = runner.send(OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="user@example.com", channel="email", text="hello"))
    assert out.channel == "email"
    assert out.mode in {"smtp", "configured_noop"}


def test_webchat_runner_returns_delivery_result():
    runner = WebChatRunner()
    out = runner.send(OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="session-1", channel="web_chat", text="hello"))
    assert out.channel == "web_chat"
    assert out.mode == "configured_noop"
