from __future__ import annotations

import json
from urllib import error as urllib_error

import pytest

import runtime._internal.effects_clients.provider_outbound_sender as sender
from tests.unit.runtime.messaging._provider_outbound_transport_support_wave28 import (
    _cfg,
    _Headers,
    _msg,
    _Response,
)


def test_result_payload_token_and_response_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    msg = _msg()

    assert sender._base_result(cfg=cfg, msg=msg) == {
        "provider": "demo",
        "delivery_key": msg.delivery_key,
    }
    failure = sender._failure_result(
        cfg=cfg,
        msg=msg,
        reason="bad",
        error=None,
        status_code=503,
    )
    assert failure["reason"] == "bad"
    assert failure["error"] == ""
    assert failure["status_code"] == 503
    assert failure["execution_state"] == "failed"

    noop = sender._noop_result(cfg=cfg, msg=msg)
    assert noop["mode"] == sender.NOOP_MODE
    assert noop["noop"] is True
    assert noop["delivery_disposition"] == "suppressed"

    values = {
        "DEMO_TOKEN": "",
        "DEMO_API_KEY": " api-key ",
        "DEMO_ACCESS_TOKEN": "access",
    }
    monkeypatch.setattr(sender, "env_str", lambda name, default="": values.get(name, default))
    assert sender._provider_token(cfg) == "api-key"
    values["DEMO_API_KEY"] = ""
    assert sender._provider_token(cfg) == "access"
    values["DEMO_ACCESS_TOKEN"] = ""
    assert sender._provider_token(cfg) == ""

    payload = sender._webhook_payload(cfg=cfg, msg=msg)
    assert payload["tenant_id"] == "tenant-1"
    assert payload["recipient"] == "recipient@example.com"
    assert payload["payload_digest"] == msg.payload_digest

    assert sender._decode_response(b"") == {}
    assert sender._decode_response(b"not-json") == {}
    assert sender._decode_response(json.dumps([1]).encode()) == {}
    assert sender._decode_response(b'{"id":"x"}') == {"id": "x"}

    assert sender._nested_external_id({"external_id": " ext "}) == "ext"
    assert sender._nested_external_id({"message_id": 42}) == "42"
    assert (
        sender._nested_external_id(
            {"messages": ["bad", {"status": "queued"}, {"delivery_id": "nested"}]}
        )
        == "nested"
    )
    assert sender._nested_external_id({"data": {"request_id": "data-id"}}) == "data-id"
    assert sender._nested_external_id({"messages": [], "data": []}) == ""

    assert sender._header_external_id(None) == ""
    assert sender._header_external_id(_Headers({"X-Request-ID": " req "})) == "req"
    assert sender._header_external_id(_Headers(fail=True)) == ""
    assert sender._header_external_id(_Headers({"X-Request-ID": ""})) == ""

    assert sender._response_is_delivered({"delivered": True}) is True
    assert sender._response_is_delivered({"status": "READ"}) is True
    assert sender._response_is_delivered({"state": "queued"}) is False

    assert sender._response_is_rejected({"ok": False}) is True
    assert sender._response_is_rejected({"success": False}) is True
    assert sender._response_is_rejected({"status": "FAILED"}) is True
    assert sender._response_is_rejected({"error": {"code": "x"}}) is True
    assert sender._response_is_rejected({"error": "bad"}) is True
    assert sender._response_is_rejected({"error": []}) is False
    assert sender._response_is_rejected({"status": "accepted"}) is False


def test_webhook_transport_covers_success_and_fail_closed_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = _msg()
    monkeypatch.setattr(sender, "env_float", lambda *_args, **_kwargs: 4.5)
    monkeypatch.setattr(sender, "env_str", lambda name, default="": "token" if name == "DEMO_TOKEN" else default)

    invalid = sender._send_webhook(cfg=_cfg(endpoint="not-a-url"), msg=msg)
    assert invalid["reason"] == "provider_endpoint_missing_or_invalid"
    bracket_invalid = sender._send_webhook(cfg=_cfg(endpoint="http://[bad"), msg=msg)
    assert bracket_invalid["reason"] == "provider_endpoint_missing_or_invalid"

    monkeypatch.setattr(
        sender.urllib_request,
        "Request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("bad")),
    )
    request_invalid = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert request_invalid["reason"] == "provider_request_invalid"
    assert request_invalid["error"] == "TypeError"
    monkeypatch.undo()
    monkeypatch.setattr(sender, "env_float", lambda *_args, **_kwargs: 4.5)
    monkeypatch.setattr(
        sender,
        "env_str",
        lambda name, default="": "token" if name == "DEMO_TOKEN" else default,
    )

    http_error = urllib_error.HTTPError("https://provider.example", 429, "rate", None, None)
    monkeypatch.setattr(sender.urllib_request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error))
    rejected_http = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert rejected_http["reason"] == "provider_http_error"
    assert rejected_http["status_code"] == 429

    monkeypatch.setattr(
        sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib_error.URLError("offline")),
    )
    transport_error = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert transport_error["reason"] == "provider_transport_error"
    assert transport_error["error"] == "URLError"

    monkeypatch.setattr(sender, "env_str", lambda _name, default="": default)
    no_token_response = _Response(body=b"{}", status=None, code=503)
    monkeypatch.setattr(
        sender.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: no_token_response,
    )
    no_token = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert no_token["reason"] == "provider_http_status_rejected"

    monkeypatch.setattr(
        sender,
        "env_str",
        lambda name, default="": "token" if name == "DEMO_TOKEN" else default,
    )
    responses = iter(
        [
            _Response(body=b"{}", status=None, code=503),
            _Response(body=b"x" * (sender._MAX_RESPONSE_BYTES + 1)),
            _Response(body=b'{"ok":false,"id":"rejected"}'),
            _Response(body=b"{}"),
            _Response(body=json.dumps({"id": msg.delivery_key}).encode()),
            _Response(body=b'{"messages":[{"id":"accepted-1"}]}'),
            _Response(
                body=b'{"data":{"id":"delivered-1"},"status":"delivered"}',
                headers=_Headers(),
            ),
            _Response(body=b"not-json", headers=_Headers({"X-Line-Request-Id": "header-1"})),
        ]
    )
    monkeypatch.setattr(sender.urllib_request, "urlopen", lambda *_args, **_kwargs: next(responses))

    assert sender._send_webhook(cfg=_cfg(), msg=msg)["reason"] == "provider_http_status_rejected"
    assert sender._send_webhook(cfg=_cfg(), msg=msg)["reason"] == "provider_response_too_large"
    assert sender._send_webhook(cfg=_cfg(), msg=msg)["reason"] == "provider_rejected_message"
    assert sender._send_webhook(cfg=_cfg(), msg=msg)["reason"] == "provider_receipt_missing"
    assert sender._send_webhook(cfg=_cfg(), msg=msg)["reason"] == "provider_receipt_not_external"

    accepted = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert accepted["ok"] is True
    assert accepted["mode"] == "accepted"
    assert accepted["external_id"] == "accepted-1"
    assert accepted["execution_state"] == "accepted"

    delivered = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert delivered["delivered"] is True
    assert delivered["mode"] == "webhook"
    assert delivered["delivery_disposition"] == "delivered"

    header_receipt = sender._send_webhook(cfg=_cfg(), msg=msg)
    assert header_receipt["external_id"] == "header-1"
    assert header_receipt["delivered"] is False


