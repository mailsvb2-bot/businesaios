from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from application.business_autonomy.provider_catalog import provider_map
from runtime._internal.http_transport import SyncHTTPResult
from runtime.business_autonomy.provider_http_live_clients import build_live_http_transports
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_runtime_write_guard import ProviderRuntimeWriteGuard
from runtime.business_autonomy.provider_transport_bindings import (
    META_GRAPH_API_VERSION,
    provider_transport_binding_for_key,
)
from runtime.handlers_messaging import _build_send_kwargs
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter, build_multichannel_dispatcher
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, business_id: str, name: str, value: str) -> None:
    ref = SecretRef(
        tenant_id="tenant-a",
        connector_id=provider.connector_id,
        scope=business_id,
        secret_name=f"{provider.connector_id}.{name}",
    )
    vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR), plaintext=value.encode())


def _env() -> SimpleNamespace:
    return SimpleNamespace(decision=SimpleNamespace(decision_id="decision-1", correlation_id="corr-1"))


def test_owner_telegram_requires_explicit_business_provider_marker() -> None:
    system = _build_send_kwargs({"tenant_id": "tenant-a", "business_id": "biz-a", "channel": "telegram", "user_id": "42", "text": "hi"}, _env())
    assert "_provider_native" not in dict(system.get("track_payload") or {})

    business = _build_send_kwargs({"tenant_id": "tenant-a", "business_id": "biz-a", "provider_key": "telegram_bot", "channel": "telegram", "chat_id": "42", "user_id": "42", "text": "hi"}, _env())
    native = dict(dict(business["track_payload"])["_provider_native"])
    assert native == {"provider_key": "telegram_bot", "business_id": "biz-a", "chat_id": "42"}

    with pytest.raises(ValueError, match="MESSAGING_PROVIDER_CHANNEL_MISMATCH"):
        _build_send_kwargs({"provider_key": "whatsapp_cloud", "channel": "telegram", "user_id": "42", "text": "hi"}, _env())


def test_multichannel_dispatcher_preserves_telegram_ownership_and_routes_whatsapp_selectively() -> None:
    dispatcher = build_multichannel_dispatcher()
    assert "telegram" not in dispatcher.adapters
    assert dispatcher.adapters["whatsapp"].native.provider_key == "whatsapp_cloud"
    assert dispatcher.adapters["whatsapp"].fallback is not None


def test_telegram_business_send_uses_scoped_vault_token_not_system_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:system-token")
    provider, vault, calls = provider_map()["telegram_bot"], InMemorySecretVault(), []
    _put(vault, provider, "biz-a", "bot_token", "123:business-token")
    monkeypatch.setattr(
        "runtime.business_autonomy.provider_http_live_clients._sync_request",
        lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"ok":true,"result":{"message_id":77}}')),
    )
    transport = build_live_http_transports(vault, bind_live_network=True)["telegram_bot"]
    blocked = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload={"chat_id": "42", "text": "hello", "_allow_network": True})
    assert blocked["_prepared_only"] is True and calls == []
    sent = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload={"chat_id": "42", "text": "hello", "_allow_network": True, "_provider_write_approved": True})
    assert sent["_response_ok"] is True
    assert calls[0]["url"] == "https://api.telegram.org/bot123:business-token/sendMessage"
    assert b'"chat_id": "42"' in calls[0]["body"] and b'"text": "hello"' in calls[0]["body"]
    assert b"system-token" not in calls[0]["body"] and "system-token" not in calls[0]["url"]
    assert sent["parsed_response"]["resource_id"] == "77"


def test_telegram_http_200_logical_error_is_not_accepted() -> None:
    parsed = ProviderResponseParsers().parse(
        provider=provider_map()["telegram_bot"],
        operation="message_send",
        response={"http_status": 200, "response_body": '{"ok":false,"error_code":403,"description":"Forbidden"}'},
    )
    assert parsed["ok"] is False
    assert parsed["error_code"] == "403"
    assert parsed["delivery_state"] == "rejected"


def test_meta_graph_bindings_share_supported_v26_contract() -> None:
    assert META_GRAPH_API_VERSION == "v26.0"
    for provider_key in ("whatsapp_cloud", "instagram_messaging", "messenger_messaging", "meta_ads"):
        binding = provider_transport_binding_for_key(provider_key)
        paths = f"{binding.get('probe_path', '')} {binding.get('sync_path_family', '')}"
        assert "/v19.0/" not in paths
        assert f"/{META_GRAPH_API_VERSION}/" in paths


def test_whatsapp_plain_text_normalizer_drops_policy_attestation_from_vendor_body() -> None:
    normalized = ProviderPayloadNormalizers().normalize_outbound(
        provider=provider_map()["whatsapp_cloud"],
        operation="message_send",
        payload={"user_id": "+79991234567", "text": "hello", "whatsapp_policy_attestation": {"recipient_opted_in": True, "customer_service_window": True}},
    )
    assert normalized == {"messaging_product": "whatsapp", "to": "79991234567", "type": "text", "text": {"body": "hello"}}


def test_whatsapp_live_send_requires_approval_policy_and_returns_provider_receipt(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    provider, vault, calls = provider_map()["whatsapp_cloud"], InMemorySecretVault(), []
    _put(vault, provider, "biz-a", "access_token", "wa-business-token")
    _put(vault, provider, "biz-a", "phone_number_id", "123456789")
    monkeypatch.setattr(
        "runtime.business_autonomy.provider_http_live_clients._sync_request",
        lambda **kwargs: (calls.append(kwargs) or SyncHTTPResult(status=200, headers={}, json={}, text='{"messaging_product":"whatsapp","contacts":[{"wa_id":"79991234567"}],"messages":[{"id":"wamid.abc"}]}')),
    )
    transport = build_live_http_transports(vault, bind_live_network=True)["whatsapp_cloud"]
    blocked = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload={"to": "79991234567", "text": "hello", "_allow_network": True})
    assert blocked["_prepared_only"] is True and calls == []
    sent = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload={"to": "79991234567", "text": "hello", "_allow_network": True, "_provider_write_approved": True})
    assert sent["_response_ok"] is True
    assert calls[0]["url"] == "https://graph.facebook.com/v26.0/123456789/messages"
    assert calls[0]["headers"]["Authorization"] == "Bearer wa-business-token"
    assert json.loads(calls[0]["body"]) == {"messaging_product": "whatsapp", "text": {"body": "hello"}, "to": "79991234567", "type": "text"}
    assert sent["parsed_response"]["resource_id"] == "wamid.abc"


def test_whatsapp_invalid_recipient_fails_before_network(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    provider, vault = provider_map()["whatsapp_cloud"], InMemorySecretVault()
    _put(vault, provider, "biz-a", "access_token", "wa-token")
    _put(vault, provider, "biz-a", "phone_number_id", "123")
    monkeypatch.setattr("runtime.business_autonomy.provider_http_live_clients._sync_request", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    result = build_live_http_transports(vault, bind_live_network=True)["whatsapp_cloud"].execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={"to": "not-a-phone", "text": "hello", "_allow_network": True, "_provider_write_approved": True},
    )
    assert result["_prepared_only"] is True
    assert result["reason"] == "native_message_send_payload_invalid"


def test_whatsapp_write_guard_requires_owner_policy_attestation_before_approval() -> None:
    provider = provider_map()["whatsapp_cloud"]
    base = {"to": "79991234567", "text": {"body": "hello"}, "_approval": {"decision_id": "d1", "execution_id": "e1"}}
    denied = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="message_send", mode="live", tenant_id="tenant-a", business_id="biz-a", payload=base)
    assert denied.allowed is False and denied.reason == "whatsapp_policy_attestation_required"
    attested = {**base, "whatsapp_policy_attestation": {"recipient_opted_in": True, "customer_service_window": True}}
    submitted = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="message_send", mode="live", tenant_id="tenant-a", business_id="biz-a", payload=attested)
    assert submitted.allowed is False and submitted.reason == "approval_submitted_awaiting_operator"


def test_native_adapter_preserves_whatsapp_policy_for_approval_but_not_as_internal_control() -> None:
    class _Registry:
        def get(self, key):
            return provider_map()[key]

    class _Service:
        provider_registry = _Registry()
        def __init__(self): self.calls = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {"dispatch": {"queued": False, "status": "rejected_provider_write_guard", "metadata": {"provider_write_guard": {"reason": "approval_submitted_awaiting_operator", "metadata": {"approval": {"approval_id": "ap-1", "approval_required": True}}}}}, "result": None}

    service = _Service()
    msg = SimpleNamespace(
        track_payload={"_provider_native": {"provider_key": "whatsapp_cloud", "business_id": "biz-a", "to": "79991234567", "whatsapp_policy_attestation": {"recipient_opted_in": True, "customer_service_window": True}}},
        business_id="biz-a", tenant_id="tenant-a", decision_id="decision-1", user_id="79991234567", text="hello", reply_markup=None, attachments=(), payload={},
    )
    result = _NativeProviderQueueAdapter("whatsapp", service_factory=lambda: service).send(msg)
    sent = service.calls[0]["payload"]
    assert sent["whatsapp_policy_attestation"] == {"recipient_opted_in": True, "customer_service_window": True}
    assert result.mode == "approval_required"


def test_whatsapp_provider_receipt_is_acceptance_not_final_delivery() -> None:
    from entrypoints.api.provider_admin_route_handlers import _approval_completion_truth

    delivered, ambiguous, terminal = _approval_completion_truth(
        provider_key="whatsapp_cloud",
        result={"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "wamid.abc"}},
    )
    assert delivered is False
    assert ambiguous is True
    assert terminal is False


def test_business_telegram_sender_uses_multichannel_provider_path_while_system_telegram_stays_native(monkeypatch) -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts import transport as transport_module

    calls: list[str] = []
    monkeypatch.setattr(transport_module, "telegram_pre_send", lambda *_args, **_kwargs: calls.append("pre"))
    monkeypatch.setattr(transport_module, "telegram_throttle", lambda *_args, **_kwargs: calls.append("throttle"))
    monkeypatch.setattr(transport_module, "telegram_delivery", lambda *_args, **_kwargs: (calls.append("system") or (True, {})))
    monkeypatch.setattr(transport_module, "multichannel_delivery", lambda *_args, **_kwargs: (calls.append("provider") or (True, {})))
    sender = transport_module.build_single_sender(SimpleNamespace())

    system = SimpleNamespace(channel="telegram", track_payload=None, user_id="42", decision_id="d1", correlation_id="c1", transport_guard=None)
    sender(system)
    assert calls == ["pre", "throttle", "system"]

    calls.clear()
    business = SimpleNamespace(channel="telegram", track_payload={"_provider_native": {"provider_key": "telegram_bot", "business_id": "biz-a", "chat_id": "42"}}, user_id="42", decision_id="d2", correlation_id="c2", transport_guard=None)
    sender(business)
    assert calls == ["provider"]


def test_owner_action_draft_maps_telegram_and_whatsapp_only_when_persisted_channel_is_explicit() -> None:
    from entrypoints.api.owner_action_draft import OwnerActionDraftProjector

    class _Ledger:
        def __init__(self, channel: str): self.channel = channel
        def read(self, _run_id):
            return {"tenant_id": "tenant-a", "business_id": "biz-a", "goal": "follow up", "canonical_run_artifact": {"step_artifacts": [{"decision_id": "d1", "action_id": "a1", "action_type": "send_message@v1", "status": "blocked_by_policy", "operator_required": True, "executed": False, "verified": False, "payload": {"channel": self.channel, "user_id": "79991234567" if self.channel == "whatsapp" else "42", "text": "hello"}}]}}

    for channel, expected in (("telegram", "telegram_bot"), ("whatsapp", "whatsapp_cloud")):
        provider = SimpleNamespace(get_runtime=lambda channel=channel: SimpleNamespace(ledger=_Ledger(channel)))
        draft = OwnerActionDraftProjector(runtime_provider=provider).project(tenant_id="tenant-a", business_id="biz-a", run_id="run-1", decision_id="d1", action_id="a1")
        assert draft["suggested_provider_key"] == expected
        assert draft["suggested_channel"] == channel


def test_whatsapp_approval_resume_replays_exact_attested_subject() -> None:
    from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers

    approved_payload = {
        "messaging_product": "whatsapp",
        "to": "79991234567",
        "type": "text",
        "text": {"body": "hello"},
        "whatsapp_policy_attestation": {"recipient_opted_in": True, "customer_service_window": True},
    }

    class _Store:
        def get(self, approval_id):
            return SimpleNamespace(status=SimpleNamespace(value="approved"), request=SimpleNamespace(approval_id=approval_id, tenant_id="tenant-a", subject_id="decision-1", metadata={"action_name": "provider.whatsapp_cloud.message_send", "decision_id": "decision-1", "approval_resume_context": {"provider_key": "whatsapp_cloud", "business_id": "biz-a", "operation": "message_send", "payload": approved_payload}}))

    class _Service:
        provider_registry = SimpleNamespace(get=lambda _self, key: provider_map()[key])
        def __init__(self): self.calls = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {"dispatch": {"queued": True, "job_id": "job-1"}, "worker": {"succeeded": 1}, "result": {"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "wamid.1"}}}

    service = _Service()
    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id="decision-1", action="send_message@v1", payload={"tenant_id": "tenant-a", "business_id": "biz-a", "channel": "whatsapp", "user_id": "79991234567", "text": "hello"}))
    result = ProviderAdminRouteHandlers(service_factory=lambda **_: service, approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope).resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
    assert result["provider_key"] == "whatsapp_cloud"
    sent = service.calls[0]["payload"]
    assert {key: value for key, value in sent.items() if key != "_approval"} == approved_payload
    assert result["execution"]["result"]["parsed_response"]["resource_id"] == "wamid.1"
