"""P1-24: VK/MAX native buttons — keyboard serialization and callback round trip."""

from __future__ import annotations

import json

import pytest

from application.business_autonomy.provider_catalog import provider_map
from core.ux.unified_messenger_menu import plain_channel_menu
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.messaging.provider_inbound_decoder import decode_provider_inbound


def _normalize(provider_key: str, reply_markup: dict, user: str = "42") -> dict:
    return ProviderPayloadNormalizers().normalize_outbound(
        provider=provider_map()[provider_key], operation="message_send",
        payload={"user_id": user, "text": "menu", "reply_markup": reply_markup})


def _menu() -> dict:
    return plain_channel_menu(channel="vk", role="owner", is_admin=True)


def test_plain_channel_menu_returns_text_actions_and_the_same_canonical_keyboard():
    page = _menu()
    flat = [b for row in page["reply_markup"]["inline_keyboard"] for b in row]
    assert [b["callback_data"] for b in flat] == [a["callback"] for a in page["actions"]]
    assert [b["text"] for b in flat] == [a["label"] for a in page["actions"]]
    assert page["text"].startswith("🏠 ClientPlatform")  # text fallback kept
    assert all(len(row) <= 2 for row in page["reply_markup"]["inline_keyboard"])


def test_vk_menu_keyboard_is_inline_callback_and_round_trips_every_action():
    page = _menu()
    keyboard = json.loads(_normalize("vk_messaging", page["reply_markup"])["keyboard"])
    assert keyboard["inline"] is True and len(keyboard["buttons"]) <= 6
    actions = [b["action"] for row in keyboard["buttons"] for b in row]
    assert {a["type"] for a in actions} == {"callback"}
    for action, expected in zip(actions, page["actions"], strict=True):
        assert action["label"] == expected["label"]
        event = {"type": "message_event", "group_id": 1, "object": {
            "event_id": "e1", "user_id": 42, "peer_id": 42, "payload": json.loads(action["payload"])}}
        assert decode_provider_inbound(channel="vk", payload=event)["text"] == expected["callback"]


def test_max_keyboard_is_off_by_default(monkeypatch):
    monkeypatch.delenv("BAI_MAX_NATIVE_BUTTONS_ENABLED", raising=False)
    assert "keyboard" not in _normalize("max_messaging", _menu()["reply_markup"])


def test_max_menu_keyboard_serializes_to_inline_keyboard_attachment_and_round_trips(monkeypatch):
    from runtime.business_autonomy.provider_http_live_clients import VendorHttpLiveTransport

    monkeypatch.setenv("BAI_MAX_NATIVE_BUTTONS_ENABLED", "1")
    page = _menu()
    normalized = _normalize("max_messaging", page["reply_markup"])
    assert "attachments" not in normalized  # never mistaken for media
    client = VendorHttpLiveTransport.__new__(VendorHttpLiveTransport)
    monkeypatch.setattr(VendorHttpLiveTransport, "_load_secrets", lambda self, **kw: {"access_token": "t"})
    monkeypatch.setattr(VendorHttpLiveTransport, "_render_url", lambda self, **kw: "https://max/messages?user_id=42")
    monkeypatch.setattr(VendorHttpLiveTransport, "_build_headers", lambda self, **kw: {})
    body = client._prepare_request(provider=provider_map()["max_messaging"], tenant_id="t", business_id="b",
                                   operation="message_send", payload=normalized, binding={})["json_body"]
    assert body["text"] == "menu"
    (attachment,) = body["attachments"]
    assert attachment["type"] == "inline_keyboard"
    buttons = [b for row in attachment["payload"]["buttons"] for b in row]
    assert [b["payload"] for b in buttons] == [a["callback"] for a in page["actions"]]
    assert {b["type"] for b in buttons} == {"callback"}
    for index, button in enumerate(buttons):
        update = {"update_type": "message_callback", "timestamp": 1, "user": {"user_id": 42},
                  "callback": {"callback_id": f"cb-{index}", "payload": button["payload"]},
                  "message": {"body": {"mid": "bot-message-1"}, "recipient": {"user_id": 42}}}
        decoded = decode_provider_inbound(channel="max", payload=update)
        assert decoded["text"] == button["payload"]
        # one identity per press, not the shared bot message id
        assert decoded["message_id"] == f"cb-{index}"
        route = ProviderWebhookRouteRegistry().extract(provider_map()["max_messaging"], {}, json.dumps(update).encode())
        assert route["messaging_ingress"]["transport_message_id"] == f"cb-{index}"


def test_max_keyboard_refuses_silent_loss(monkeypatch):
    monkeypatch.setenv("BAI_MAX_NATIVE_BUTTONS_ENABLED", "1")
    too_wide = {"inline_keyboard": [[{"text": f"B{i}", "callback_data": f"c:{i}"} for i in range(8)]]}
    with pytest.raises(ValueError, match="capacity"):
        _normalize("max_messaging", too_wide)
    with pytest.raises(ValueError, match="payload"):
        _normalize("max_messaging", {"inline_keyboard": [[{"text": "x", "callback_data": "x" * 1025}]]})
    links = _normalize("max_messaging", {"inline_keyboard": [[{"text": "Сайт", "url": "https://example.ru"}]]})
    assert links["keyboard"] == [[{"type": "link", "text": "Сайт", "url": "https://example.ru"}]]


class _Vault:
    def get(self, ref):
        if ref.secret_name.endswith("access_token"):
            return b"max-token"
        raise KeyError(ref.secret_name)


def test_max_callback_is_answered_only_behind_the_flag(monkeypatch):
    from runtime.business_autonomy import provider_webhook_reconciliation as rec

    calls = []
    monkeypatch.setattr(rec.ProviderWebhookReconciler, "_json_request",
                        staticmethod(lambda **kw: calls.append(kw) or {"success": True}))
    responder = rec.ProviderWebhookOperationalResponder(_Vault())
    handoff = {"inbound_message": {"transport_message_id": "cb-1", "user_id": "42", "chat_id": "42"}}
    out = responder.acknowledge(provider=provider_map()["max_messaging"], tenant_id="t", business_id="b",
                                topic="message_callback", handoff=handoff)
    assert out == {"required": True, "ok": True, "kind": "max_callback_answer", "callback_id": "cb-1"}
    assert calls[0]["url"].endswith("/answers?callback_id=cb-1")
    assert calls[0]["headers"] == {"Authorization": "max-token"}
    calls.clear()
    monkeypatch.setattr(rec.ProviderWebhookReconciler, "_json_request", staticmethod(lambda **kw: {"success": False}))
    assert responder.acknowledge(provider=provider_map()["max_messaging"], tenant_id="t", business_id="b",
                                 topic="message_callback", handoff=handoff)["ok"] is False
