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
    assert [name for name, _args in smtp.calls] == ["ehlo", "starttls", "ehlo", "login", "send_message", "quit"]
    assert smtp.message is not None
    assert smtp.message["From"] == "sender@example.com"
    assert smtp.message["To"] == "recipient@example.com"
    assert smtp.message["Subject"] == "Subject"

    class RefusingSMTP(_SMTP):
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            super().__init__(host, port, timeout=timeout, refused={"recipient": 550}, fail_quit=True)

    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", RefusingSMTP)
    refused = sender._send_smtp(cfg=_cfg(mode="smtp", endpoint="smtps://secure.example"), msg=msg)
    assert refused["reason"] == "smtp_recipient_refused"
    secure_client = RefusingSMTP.instances[-1]
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


