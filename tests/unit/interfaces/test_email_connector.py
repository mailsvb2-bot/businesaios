from __future__ import annotations

from interfaces.common.auth_session import AuthSession
from interfaces.communications.email_connector import EmailConnector


def test_email_connector_executes_and_verifies_when_configured() -> None:
    connector = EmailConnector(session=AuthSession(configured=True))
    result = connector.execute("send_email", {"to": "user@example.com"}, idempotency_key="msg-1")
    assert result.ok is True
    verify = connector.verify("send_email", {"to": "user@example.com"}, result.payload)
    assert verify.ok is True
    assert verify.payload["external_ref"] == "email:msg-1"
