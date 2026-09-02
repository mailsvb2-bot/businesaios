from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from entrypoints.api.approval_route_support import resume_hint
from interfaces.web.settings.alert_subscriptions.form_parser import parse_alert_subscriptions_form
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.bridge import _bind_native_provider_context
from runtime.messaging.outbound_message import OutboundMessage
from security.secret_contract import SecretRef
from security.secret_vault import InMemorySecretVault

META_CASES = (
    ("instagram", "instagram_messaging", "ig_user_id", "1784140001", "https://graph.instagram.com/v26.0/1784140001/messages"),
    ("messenger", "messenger_messaging", "page_id", "123456789", "https://graph.facebook.com/v26.0/123456789/messages"),
)


def _msg(channel: str, *, business_id: str = "biz-a", user_id: str = "recipient-1", track_payload: dict | None = None) -> OutboundMessage:
    return OutboundMessage(
        decision_id="dec-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        business_id=business_id,
        user_id=user_id,
        channel=channel,
        text="hello",
        track_payload=track_payload,
    )


@pytest.mark.parametrize("channel,key,owner_field,_owner_id,_url", META_CASES)
def test_meta_provider_contract_adds_optional_native_credentials_without_fake_live_readiness(channel, key, owner_field, _owner_id, _url):
    provider = provider_map()[key]
    fields = {field.secret_name: field for field in provider.secret_fields}
    assert fields["webhook_secret"].required is True
    assert fields["access_token"].required is False
    assert fields[owner_field].required is False
    assert ProviderSyncRuntimePlanner().describe(provider).write_operations == ("message_send",)
    binding = provider_transport_binding_for_key(key)
    assert binding["live_probe_ready"] is False
    assert binding["live_read_ready"] is False
    assert binding["live_ready"] is False
    truth = provider_truth_map()[key]
    assert truth.write_supported is True
    assert truth.live_ready is False
    assert truth.has_real_endpoint is True
    assert {"webhook_secret", "access_token", owner_field} <= set(truth.health_requirements)


@pytest.mark.parametrize("channel,key,owner_field,owner_id,url", META_CASES)
def test_meta_prepared_send_matches_official_text_message_contract(channel, key, owner_field, owner_id, url):
    provider = provider_map()[key]
    request = build_provider_vendor_transports()[key].execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={"recipient_id": "recipient-1", "text": "hello", owner_field: owner_id},
    )["request"]
    assert request["method"] == "POST"
    assert request["url_template"] == url.replace(owner_id, "{" + owner_field + "}")
    assert request["headers"] == {"Authorization": "Bearer {access_token}"}
    expected = {"recipient": {"id": "recipient-1"}, "message": {"text": "hello"}}
    if channel == "messenger":
        expected["messaging_type"] = "RESPONSE"
    assert request["json_body"] == expected
    with pytest.raises(ValueError, match="webhook-driven"):
        build_provider_vendor_transports()[key].execute(
            provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_read", payload={}
        )


@pytest.mark.parametrize("channel,key,owner_field,owner_id,url", META_CASES)
def test_meta_live_send_is_approval_gated_and_preserves_message_receipt(monkeypatch, channel, key, owner_field, owner_id, url):
    provider = provider_map()[key]
    vault = InMemorySecretVault()
    for secret_name, value in (("access_token", "meta-token"), (owner_field, owner_id)):
        vault.seed_plaintext(
            ref=SecretRef(
                tenant_id="tenant-a",
                connector_id=provider.connector_id,
                scope="biz-a",
                secret_name=f"{provider.connector_id}.{secret_name}",
            ),
            plaintext=value,
        )
    calls = []

    def fake_sync_request(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status=200,
            text=json.dumps({"recipient_id": "recipient-1", "message_id": "mid-123"}),
            headers={"x-fb-request-id": "req-1", "x-business-use-case-usage": "{}"},
            error_kind=None,
            error_message=None,
        )

    monkeypatch.setattr("runtime.business_autonomy.provider_http_live_clients._sync_request", fake_sync_request)
    transport = build_live_http_transports(vault, bind_live_network=True)[key]
    blocked = transport.execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={"recipient_id": "recipient-1", "text": "hello", "_allow_network": True},
    )
    assert blocked["_prepared_only"] is True
    assert calls == []

    result = transport.execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={
            "recipient_id": "recipient-1",
            "text": "hello",
            "_allow_network": True,
            "_provider_write_approved": True,
        },
    )
    assert len(calls) == 1
    assert calls[0]["url"] == url
    assert calls[0]["headers"]["Authorization"] == "Bearer meta-token"
    assert result["request"]["headers"]["Authorization"] == "***"
    assert result["parsed_response"]["resource_id"] == "mid-123"
    assert result["parsed_response"]["delivery_state"] == "accepted"
    assert result["response_headers"]["x-fb-request-id"] == "req-1"


@pytest.mark.parametrize("channel,key,_owner_field,_owner_id,_url", META_CASES)
def test_meta_native_bridge_binds_recipient_and_queue_has_no_generic_fallback(channel, key, _owner_field, _owner_id, _url):
    bound = _bind_native_provider_context(_msg(channel, user_id="recipient-1"))
    assert bound.track_payload["_provider_native"] == {
        "provider_key": key,
        "business_id": "biz-a",
        "recipient_id": "recipient-1",
    }
    adapter = _NativeProviderQueueAdapter(
        channel,
        service_factory=lambda: (_ for _ in ()).throw(AssertionError("service must not run without native context")),
    )
    no_context = adapter.send(_msg(channel, track_payload=None))
    assert no_context.ok is False and no_context.detail["reason"] == "native_context_required"


@pytest.mark.parametrize("channel,key,_owner_field,_owner_id,_url", META_CASES)
def test_meta_native_adapter_requires_business_and_recipient_before_service(channel, key, _owner_field, _owner_id, _url):
    adapter = _NativeProviderQueueAdapter(
        channel,
        service_factory=lambda: (_ for _ in ()).throw(AssertionError("service must not run for invalid native context")),
    )
    missing_business = adapter.send(
        _msg(channel, business_id="", track_payload={"_provider_native": {"provider_key": key, "recipient_id": "recipient-1"}})
    )
    assert missing_business.detail["reason"] == "native_business_id_required"
    missing_recipient = adapter.send(
        _msg(channel, track_payload={"_provider_native": {"provider_key": key, "business_id": "biz-a"}})
    )
    assert missing_recipient.detail["reason"] == "native_recipient_id_required"


@pytest.mark.parametrize("channel,key,_owner_field,_owner_id,_url", META_CASES)
def test_meta_approval_resume_and_alert_configuration_use_canonical_guarded_path(channel, key, _owner_field, _owner_id, _url):
    hint = resume_hint({"status": "approved", "action_name": f"provider.{key}.message_send", "approval_id": "ap-1"})
    assert hint["resume_action"] == "/control-plane/provider-runtime/approval-resume"
    with pytest.raises(ValueError, match="business_id is required"):
        parse_alert_subscriptions_form({"items": [{"recipient_user_id": "recipient-1", "channel": channel}]})
    saved = parse_alert_subscriptions_form(
        {"items": [{"recipient_user_id": "recipient-1", "channel": channel, "business_id": "biz-a"}]}
    )
    assert saved[0]["business_id"] == "biz-a"
