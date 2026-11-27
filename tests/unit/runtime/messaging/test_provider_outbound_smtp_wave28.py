from __future__ import annotations

import pytest

import runtime._internal.effects_clients.provider_outbound_sender as sender
from tests.unit.runtime.messaging._provider_outbound_transport_support_wave28 import (
    _SMTP,
    _cfg,
    _msg,
)


def test_smtp_coordinates_headers_and_transport_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = _msg()
    assert sender._smtp_coordinates(_cfg(endpoint="mail.example:2525")) == ("mail.example", 2525, False)
    assert sender._smtp_coordinates(_cfg(endpoint="smtps://mail.example")) == ("mail.example", 465, True)
    assert sender._smtp_coordinates(_cfg(endpoint="https://mail.example")) == ("", 0, False)
    assert sender._smtp_coordinates(_cfg(endpoint="smtp://mail.example:bad")) == ("", 0, False)
    assert sender._safe_header(" value ") == "value"
    assert sender._safe_header("bad\r\nheader") == ""

    env: dict[str, object] = {
        "DEMO_USERNAME": "user",
        "DEMO_PASSWORD": "password",
        "DEMO_SUBJECT": "Default subject",
        "DEMO_STARTTLS": True,
    }
    monkeypatch.setattr(sender, "env_str", lambda name, default="": str(env.get(name, default)))
    monkeypatch.setattr(sender, "env_bool", lambda name, default=False: bool(env.get(name, default)))
    monkeypatch.setattr(sender, "env_float", lambda *_args, **_kwargs: 9.0)
    monkeypatch.setattr(sender, "make_msgid", lambda *, domain=None: f"<id@{domain or 'local'}>")

    missing = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="", sender_value=""), msg=msg)
    assert missing["reason"] == "smtp_coordinates_missing"

    env["DEMO_PASSWORD"] = ""
    incomplete = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="smtp://mail.example"), msg=msg)
    assert incomplete["reason"] == "smtp_credentials_incomplete"
    env["DEMO_PASSWORD"] = "password"

    invalid_recipient = sender._send_smtp(
        cfg=_cfg(mode="smtp", endpoint="smtp://mail.example"),
        msg=_msg(user_id="bad\nrecipient"),
    )
    assert invalid_recipient["reason"] == "smtp_coordinates_missing"

    invalid_subject = sender._send_smtp(
        cfg=_cfg(mode="smtp", endpoint="smtp://mail.example"),
        msg=_msg(payload={"subject": "bad\nsubject"}),
    )
    assert invalid_subject["reason"] == "smtp_header_invalid"

    _SMTP.instances.clear()
    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", _SMTP)
    accepted = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="smtp://mail.example:2525"), msg=msg)
    assert accepted["ok"] is True
    assert accepted["accepted"] is True
    assert accepted["external_id"] == "<id@example.com>"
    smtp = _SMTP.instances[-1]
    assert smtp.host == "mail.example" and smtp.port == 2525 and smtp.timeout == 9.0
    assert smtp.starttls_context is not None and smtp.starttls_context.check_hostname is True
    assert [name for name, _args in smtp.calls] == ["ehlo", "starttls", "ehlo", "login", "send_message", "quit"]
    assert smtp.message is not None
    assert smtp.message["From"] == "sender@example.com"
    assert smtp.message["To"] == "recipient@example.com"
    assert smtp.message["Subject"] == "Subject"

    class RefusingSMTP(_SMTP):
        def __init__(self, host: str, port: int, *, timeout: float, context=None) -> None:
            super().__init__(host, port, timeout=timeout, context=context, refused={"recipient": 550}, fail_quit=True)

    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", RefusingSMTP)
    refused = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="smtps://secure.example"), msg=msg)
    assert refused["reason"] == "smtp_recipient_refused"
    secure_client = RefusingSMTP.instances[-1]
    assert secure_client.context is not None and secure_client.context.check_hostname is True
    assert not any(name == "starttls" for name, _args in secure_client.calls)

    env["DEMO_USERNAME"] = ""
    env["DEMO_PASSWORD"] = ""
    env["DEMO_STARTTLS"] = False
    _SMTP.instances.clear()
    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    no_credentials = sender._send_smtp(
        cfg=_cfg(mode="smtp", endpoint="smtp://mail.example"),
        msg=msg,
    )
    assert no_credentials["ok"] is True
    no_credentials_client = _SMTP.instances[-1]
    assert not any(name == "login" for name, _args in no_credentials_client.calls)
    assert not any(name == "starttls" for name, _args in no_credentials_client.calls)

    class FailingSMTP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise sender.smtplib.SMTPException("offline")

    monkeypatch.setattr(sender.smtplib, "SMTP", FailingSMTP)
    failed = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="smtp://mail.example"), msg=msg)
    assert failed["reason"] == "smtp_transport_error"
    assert failed["error"] == "SMTPException"


def test_smtp_transport_guard_rechecks_after_handshake_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {"DEMO_STARTTLS": False}
    monkeypatch.setattr(sender, "env_str", lambda _name, default="": default)
    monkeypatch.setattr(sender, "env_bool", lambda name, default=False: bool(env.get(name, default)))
    monkeypatch.setattr(sender, "env_float", lambda *_args, **_kwargs: 9.0)
    _SMTP.instances.clear()
    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    checks = iter(("", "", "preference_changed"))
    result = sender._send_smtp(
        cfg=_cfg(mode="smtp", endpoint="smtp://mail.example:2525"),
        msg=_msg(transport_guard=lambda _msg: next(checks)),
    )
    assert result["mode"] == "blocked"
    assert result["delivery_disposition"] == "suppressed"
    assert [name for name, _args in _SMTP.instances[-1].calls] == ["ehlo", "quit"]


def test_smtp_transport_guard_precedes_provider_validation() -> None:
    result = sender._send_smtp(
        cfg=_cfg(mode="smtp", endpoint="", sender_value=""),
        msg=_msg(transport_guard=lambda _msg: "preference_changed"),
    )
    assert result["mode"] == "blocked"
    assert result["delivery_disposition"] == "suppressed"

def _live_smtp_security_parts(monkeypatch):
    from application.business_autonomy.channel_contracts import ChannelKind
    from application.business_autonomy.provider_admin_contract import ProviderDefinition
    from runtime.business_autonomy import provider_smtp_live_client as smtp_mod
    from runtime.business_autonomy.provider_smtp_live_client import ProviderSmtpLiveTransport
    from security.secret_contract import SecretRecord, SecretRef, SecretSource
    from security.secret_vault import InMemorySecretVault

    provider = ProviderDefinition(
        provider_key="email_connector", title="Email", connector_id="email_connector",
        adapter_key="smtp", channel_kind=ChannelKind.CHATBOT, domain="email",
        description="smtp", secret_fields=(),
    )
    vault = InMemorySecretVault()
    values = {
        "smtp_host": "smtp.example.org", "smtp_port": "587",
        "smtp_security": "starttls", "smtp_username": "mailer",
        "smtp_password": "vault-password", "from_address": "shop@example.org",
    }
    for name, value in values.items():
        ref = SecretRef(
            tenant_id="tenant-a", connector_id="email_connector", scope="biz-a",
            secret_name=f"email_connector.{name}",
        )
        vault.put(
            SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR),
            plaintext=value.encode(),
        )
    calls = []

    class SmtpExplicitError(Exception):
        pass

    def fake_import(_module, name):
        if name == "smtp_send_explicit":
            return lambda **kwargs: calls.append(kwargs) or {
                "accepted": True, "message_id": "smtp-message-1",
            }
        if name == "SmtpExplicitError":
            return SmtpExplicitError
        raise AssertionError(f"unexpected SMTP import: {name}")

    monkeypatch.setattr(smtp_mod, "import_internal_attr", fake_import)
    return provider, vault, calls, ProviderSmtpLiveTransport


def test_live_smtp_uses_tenant_vault_password_not_payload_password(monkeypatch):
    provider, vault, calls, transport_type = _live_smtp_security_parts(monkeypatch)
    transport = transport_type(secret_vault=vault, bind_live_network=True)
    out = transport.execute(
        provider=provider, tenant_id="tenant-a", business_id="biz-a",
        operation="message_send",
        payload={
            "recipient": "client@example.org", "subject": "hello", "body": "message",
            "_allow_network": True, "_provider_write_approved": True,
            "_provider_queue_job_id": "queue-job-1",
            "smtp_password": "attacker-payload-secret", "password": "attacker-payload-secret",
        },
    )
    assert out["_response_ok"] is True
    assert [call["password"] for call in calls] == ["vault-password"]
    assert "attacker-payload-secret" not in repr(calls)
    assert "attacker-payload-secret" not in repr(out)


def test_live_smtp_requires_explicit_write_approval_and_queue_identity(monkeypatch):
    provider, vault, calls, transport_type = _live_smtp_security_parts(monkeypatch)
    transport = transport_type(secret_vault=vault, bind_live_network=True)
    base = {
        "recipient": "client@example.org", "subject": "hello", "body": "message",
        "_allow_network": True, "_provider_queue_job_id": "queue-job-1",
    }
    refused = transport.execute(
        provider=provider, tenant_id="tenant-a", business_id="biz-a",
        operation="message_send", payload=base,
    )
    assert refused["_prepared_only"] is True
    assert refused["reason"] == "smtp_write_approval_required"
    no_queue = transport.execute(
        provider=provider, tenant_id="tenant-a", business_id="biz-a",
        operation="message_send",
        payload={**base, "_provider_write_approved": True, "_provider_queue_job_id": ""},
    )
    assert no_queue["parsed_response"]["error_code"] == "smtp_queue_identity_missing"
    not_bound = transport_type(secret_vault=vault, bind_live_network=False).execute(
        provider=provider, tenant_id="tenant-a", business_id="biz-a",
        operation="message_send",
        payload={**base, "_provider_write_approved": True},
    )
    assert not_bound["_prepared_only"] is True
    assert calls == []


def test_live_smtp_foreign_tenant_cannot_read_credentials_or_send(monkeypatch):
    provider, vault, calls, transport_type = _live_smtp_security_parts(monkeypatch)
    transport = transport_type(secret_vault=vault, bind_live_network=True)
    out = transport.execute(
        provider=provider, tenant_id="tenant-b", business_id="biz-a",
        operation="message_send",
        payload={
            "recipient": "client@example.org", "subject": "hello", "body": "message",
            "_allow_network": True, "_provider_write_approved": True,
            "_provider_queue_job_id": "queue-job-1",
        },
    )
    assert out["_response_ok"] is False
    assert calls == []
