from __future__ import annotations

from interfaces.common.auth_session import AuthSession
from interfaces.communications.email_connector import EmailConnector


def test_email_connector_is_dry_run_facade_and_never_fakes_live_success() -> None:
    connector = EmailConnector(session=AuthSession(configured=True))
    live = connector.execute("send_email", {"to": "user@example.com"}, idempotency_key="msg-1")
    assert live.ok is False and live.code == "canonical_provider_runtime_required"
    dry = connector.execute("send_email", {"to": "User@Example.COM"}, idempotency_key="msg-1", dry_run=True)
    assert dry.ok is True and dry.code == "prepared_dry_run"
    assert dry.payload["recipient"] == "user@example.com" and dry.payload["delivery_state"] == "not_attempted"
    missing = connector.verify("send_email", {"to": "user@example.com"}, dry.payload)
    assert missing.ok is False and missing.code == "provider_evidence_required"
    accepted = connector.verify(
        "send_email",
        {"to": "user@example.com"},
        {"recipient": "user@example.com", "provider_message_id": "<msg@example.com>", "provider_accepted": True},
    )
    assert accepted.ok is True and accepted.code == "provider_accepted"
    assert accepted.payload["delivery_state"] == "accepted" and accepted.payload["independently_verified"] is False


def test_email_connector_does_not_claim_inbox_read_support() -> None:
    connector = EmailConnector(session=AuthSession(configured=True))
    assert connector.capabilities()["read"] is False
