from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from entrypoints.api.approval_route_support import resume_hint
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.bridge import _bind_native_provider_context
from runtime.messaging.outbound_message import OutboundMessage
from security.secret_contract import SecretRef
from security.secret_vault import InMemorySecretVault

CASES = (
    ("line", "line_messaging", "channel_access_token", "line-token", "to", "line-user-1"),
    ("viber", "viber_messaging", "auth_token", "viber-token", "receiver", "viber-user-1"),
)


def _message(channel: str, *, user_id: str, track_payload=None) -> OutboundMessage:
    return OutboundMessage(
        decision_id="dec-line-viber",
        correlation_id="corr-line-viber",
        tenant_id="tenant-a",
        business_id="biz-a",
        user_id=user_id,
        channel=channel,
        text="hello",
        track_payload=track_payload,
    )


def _seed(vault, provider, secret_name: str, value: str) -> None:
    vault.seed_plaintext(
        ref=SecretRef(
            tenant_id="tenant-a",
            connector_id=provider.connector_id,
            scope="biz-a",
            secret_name=f"{provider.connector_id}.{secret_name}",
        ),
        plaintext=value,
    )


@pytest.mark.parametrize("channel,key,token_name,_token,_recipient_key,_recipient", CASES)
def test_line_viber_truth_is_guarded_write_without_fake_readiness(channel, key, token_name, _token, _recipient_key, _recipient):
    provider = provider_map()[key]
    fields = {field.secret_name: field for field in provider.secret_fields}
    assert token_name in fields
    truth = provider_truth_map()[key]
    assert truth.write_supported is True
    assert truth.approval_required is True
    assert truth.live_ready is False
    assert truth.read_only_supported is True
    assert provider_transport_binding_for_key(key)["live_read_ready"] is False


@pytest.mark.parametrize("channel,key,_token_name,_token,recipient_key,recipient", CASES)
def test_line_viber_prepared_send_uses_official_vendor_contract(channel, key, _token_name, _token, recipient_key, recipient):
    provider = provider_map()[key]
    request = build_provider_vendor_transports()[key].execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={recipient_key: recipient, "text": "hello"},
    )["request"]
    assert request["method"] == "POST"
    if channel == "line":
        assert request["url_template"] == "https://api.line.me/v2/bot/message/push"
        assert request["headers"] == {"Authorization": "Bearer {channel_access_token}"}
        assert request["json_body"] == {"to": recipient, "messages": [{"type": "text", "text": "hello"}]}
    else:
        assert request["url_template"] == "https://chatapi.viber.com/pa/send_message"
        assert request["headers"] == {"X-Viber-Auth-Token": "{auth_token}"}
        assert request["json_body"]["receiver"] == recipient
        assert request["json_body"]["type"] == "text"
        assert request["json_body"]["text"] == "hello"


@pytest.mark.parametrize("channel,key,token_name,token,recipient_key,recipient", CASES)
def test_line_viber_live_send_requires_approval_marker_and_preserves_external_receipt(monkeypatch, channel, key, token_name, token, recipient_key, recipient):
    provider = provider_map()[key]
    vault = InMemorySecretVault()
    _seed(vault, provider, token_name, token)
    if channel == "viber":
        _seed(vault, provider, "sender_name", "Business")
    calls = []

    def fake_sync_request(**kwargs):
        calls.append(kwargs)
        if channel == "line":
            return SimpleNamespace(status=200, text="{}", headers={"x-line-request-id": "line-request-1"}, error_kind=None, error_message=None)
        return SimpleNamespace(status=200, text=json.dumps({"status": 0, "status_message": "ok", "message_token": 987654}), headers={}, error_kind=None, error_message=None)

    monkeypatch.setattr("runtime.business_autonomy.provider_http_live_clients._sync_request", fake_sync_request)
    transport = build_live_http_transports(vault, bind_live_network=True)[key]
    blocked = transport.execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={recipient_key: recipient, "text": "hello", "_allow_network": True},
    )
    assert blocked["_prepared_only"] is True and calls == []
    sent = transport.execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={recipient_key: recipient, "text": "hello", "_allow_network": True, "_provider_write_approved": True},
    )
    assert len(calls) == 1
    assert sent["parsed_response"]["resource_id"] == ("line-request-1" if channel == "line" else "987654")
    assert sent["parsed_response"]["delivery_state"] == "accepted"


def test_viber_live_send_without_sender_name_fails_closed_before_network(monkeypatch):
    provider = provider_map()["viber_messaging"]
    vault = InMemorySecretVault()
    _seed(vault, provider, "auth_token", "viber-token")
    monkeypatch.setattr("runtime.business_autonomy.provider_http_live_clients._sync_request", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    result = build_live_http_transports(vault, bind_live_network=True)["viber_messaging"].execute(
        provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send",
        payload={"receiver": "viber-user-1", "text": "hello", "_allow_network": True, "_provider_write_approved": True},
    )
    assert result["_prepared_only"] is True
    assert result["reason"] == "native_message_send_payload_invalid"


@pytest.mark.parametrize("channel,key,_token_name,_token,recipient_key,recipient", CASES)
def test_line_viber_bridge_binds_scoped_recipient_and_queue_uses_canonical_service(channel, key, _token_name, _token, recipient_key, recipient):
    bound = _bind_native_provider_context(_message(channel, user_id=recipient))
    assert bound.track_payload["_provider_native"] == {
        "provider_key": key,
        "business_id": "biz-a",
        recipient_key: recipient,
    }
    calls = []

    class _Registry:
        def get(self, provider_key):
            return provider_map()[provider_key]

    class _Service:
        provider_registry = _Registry()
        def execute_queued_provider_sync(self, **kwargs):
            calls.append(kwargs)
            return {
                "dispatch": {"queued": True, "job_id": "job-1"},
                "result": {"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "provider-receipt-1"}},
            }

    result = _NativeProviderQueueAdapter(channel, service_factory=lambda: _Service()).send(bound)
    assert result.ok is True and result.external_id == "provider-receipt-1"
    assert calls[0]["provider_key"] == key and calls[0]["operation"] == "message_send" and calls[0]["mode"] == "live"
    assert calls[0]["payload"][recipient_key] == recipient
    assert calls[0]["payload"]["_approval"]["decision_id"] == "dec-line-viber"


@pytest.mark.parametrize("channel,key,_token_name,_token,_recipient_key,_recipient", CASES)
def test_line_viber_approval_resume_uses_existing_provider_runtime_path(channel, key, _token_name, _token, _recipient_key, _recipient):
    hint = resume_hint({"status": "approved", "action_name": f"provider.{key}.message_send", "approval_id": "ap-1"})
    assert hint["resume_action"] == "/control-plane/provider-runtime/approval-resume"
