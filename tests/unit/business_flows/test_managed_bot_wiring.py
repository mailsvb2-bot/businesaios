"""Managed-bot production wiring: update parsing -> route -> handler; token effect + poll effect, fakes only."""

from __future__ import annotations

import json
from functools import partial
from types import SimpleNamespace

import pytest

from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
from interfaces.telegram.parsing.telegram_context import build_context
from interfaces.telegram.runtime.worldstate_overlays import build_overlays_from_context
from runtime._internal import effect_payloads
from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions import telegram_actions_polling as tap
from runtime.handler_impl.domains.bot_provisioning_ops import handle_bot_provisioning, managed_bot_token_source
from security.secret_vault import InMemorySecretVault

TOKEN = "777:FAKE-secret-token-value"
UPDATE = {
    "update_id": 41,
    "managed_bot": {
        "user": {"id": 5001, "is_bot": False, "first_name": "Owner"},
        "bot": {"id": 777, "is_bot": True, "first_name": "Shop", "username": "Shop_Helper_bot"},
    },
}


def test_managed_bot_update_parses_to_trusted_session():
    ctx = build_context(UPDATE)
    assert ctx is not None and ctx.chat_id == "5001" and ctx.command is None
    assert ctx.managed_bot == {"user_id": "5001", "bot_id": "777", "username": "Shop_Helper_bot"}
    session = build_overlays_from_context(ctx=ctx).session
    assert session["source"] == "managed_bot_update" and session["managed_bot"]["bot_id"] == "777"


@pytest.mark.parametrize(
    "bad",
    [
        {"user": {"id": 1}, "bot": {"id": 2, "is_bot": False}},
        {"user": {"id": "x"}, "bot": {"id": 2, "is_bot": True}},
        "not-a-dict",
    ],
)
def test_malformed_managed_bot_update_is_not_trusted(bad):
    ctx = build_context({"update_id": 1, "managed_bot": bad})
    assert ctx is None or ctx.managed_bot is None


def test_user_text_cannot_forge_managed_bot_source():
    ctx = build_context({"update_id": 2, "message": {"message_id": 1, "chat": {"id": 5}, "text": "/managed_bot 777 x"}})
    assert "source" not in build_overlays_from_context(ctx=ctx).session


def test_route_proposes_managed_event():
    session = {"source": "managed_bot_update", "managed_bot": {"bot_id": "777", "username": "Shop_Helper_bot"}}
    ctx = SimpleNamespace(state=SimpleNamespace(session=session), callback_data="", callback_query_id=None,
                          args="", cmd=None, is_admin=False)  # fmt: skip
    out = handle_business_flow_routes(ctx, user_id="5001")
    assert out.action == "bot_provisioning@v1"
    assert out.payload["op"] == "managed_event" and out.payload["arg"] == "777 Shop_Helper_bot"


class FakeTelegram:
    def __init__(self, bot_id=777):
        self.bot_id, self.calls = bot_id, []

    def __call__(self, *, token=None, clear_webhook=False):
        self.calls.append(clear_webhook)
        return {"ok": True, "bot": {"id": self.bot_id, "is_bot": True, "username": "shop_helper_bot"}}


def _effects_token(ok=True):
    calls = []

    def fetch(*, managed_bot_id):
        calls.append(managed_bot_id)
        return {"ok": True, "token": TOKEN} if ok else {"ok": False, "error": "managed_bot_token_unavailable"}

    return fetch, calls


def _event(flow, vault, *, ok=True, bot_id=777):
    flow.effects.telegram_self_check = FakeTelegram(bot_id)
    fetch, calls = _effects_token(ok)
    flow.effects.telegram_managed_bot_token = fetch
    run = partial(handle_bot_provisioning, vault=vault, token_source=managed_bot_token_source(flow.effects))
    flow.run(run, op="managed_begin")
    _, text = flow.run(run, op="managed_event", arg="777 Shop_Helper_bot")
    return text, calls


def test_managed_event_completes_through_token_effect(flow):
    vault = InMemorySecretVault()
    text, calls = _event(flow, vault)
    assert "подключён" in text and calls == ["777"]
    last = flow.store.events[-1]["payload"]
    assert last["status"] == "completed" and last["credential_ref"] == "vault:managed_bot.777"
    assert last["username"] == "shop_helper_bot" and last["external_bot_id"] == "777"
    assert TOKEN not in json.dumps([e["payload"] for e in flow.store.events])


def test_managed_event_token_failure_stores_nothing_secret(flow):
    text, _ = _event(flow, InMemorySecretVault(), ok=False)
    assert "managed_bot_token_fetch_failed" in text
    assert [e["payload"]["status"] for e in flow.store.events] == ["awaiting_bot"]


def test_managed_event_identity_mismatch_rolls_back(flow):
    vault = InMemorySecretVault()
    _event(flow, vault, bot_id=999)
    last = flow.store.events[-1]["payload"]
    assert last["status"] == "failed" and last["rolled_back"] and last["credential_ref"] == ""


def test_self_check_payload_keeps_clear_webhook():
    out = effect_payloads.normalize_effect_payload(EffectActionType.TELEGRAM_SELF_CHECK, {"token": "t", "clear_webhook": True})
    assert out == {"token": "t", "clear_webhook": True}


@pytest.fixture
def fake_http(monkeypatch):
    calls = []

    def http_json(method, url, params, **_):
        calls.append((url.rsplit("/", 1)[-1], dict(params or {})))
        if url.endswith("getManagedBotToken"):
            return {"ok": True, "result": TOKEN}
        return {"ok": True, "result": [{"update_id": 9}]}

    monkeypatch.setattr(tap, "http_json", http_json)
    monkeypatch.setattr(tap, "is_telegram_mode", lambda: True)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "100:MANAGER")
    return calls


def test_managed_bot_token_effect_uses_manager_bot(fake_http):
    assert tap.managed_bot_token_effect(SimpleNamespace(), managed_bot_id="777") == {"ok": True, "token": TOKEN}
    assert fake_http == [("getManagedBotToken", {"user_id": "777"})]
    assert tap.managed_bot_token_effect(SimpleNamespace(), managed_bot_id="x")["ok"] is False


def test_tenant_poll_skips_platform_startup_and_filter(fake_http, monkeypatch):
    monkeypatch.setenv("TELEGRAM_MANAGED_BOTS_ENABLED", "1")
    out = tap.poll_telegram_updates_effect(SimpleNamespace(), offset=3, timeout_s=0, limit=5, token="777:T")
    assert out["updates"] == [{"update_id": 9}]
    assert fake_http == [("getUpdates", {"timeout": 0, "limit": 5, "offset": 3})]


def test_longpoll_entrypoint_requests_managed_bot_only_when_enabled(monkeypatch):
    from runtime.integration.managed_bot_updates import allowed_updates_param

    monkeypatch.delenv("TELEGRAM_MANAGED_BOTS_ENABLED", raising=False)
    assert allowed_updates_param() == {}
    monkeypatch.setenv("TELEGRAM_MANAGED_BOTS_ENABLED", "1")
    assert "managed_bot" in json.loads(allowed_updates_param()["allowed_updates"])
    assert allowed_updates_param(tenant=True) == {}


def test_platform_poll_opt_in_requests_managed_bot_updates(fake_http, monkeypatch):
    eff = SimpleNamespace(_telegram_startup_checked=True)
    tap.poll_telegram_updates_effect(eff, timeout_s=0, limit=5)
    assert "allowed_updates" not in fake_http[-1][1]  # default: Bot API behaviour unchanged
    monkeypatch.setenv("TELEGRAM_MANAGED_BOTS_ENABLED", "1")
    tap.poll_telegram_updates_effect(eff, timeout_s=0, limit=5)
    assert "managed_bot" in json.loads(fake_http[-1][1]["allowed_updates"])


def test_managed_bot_update_reaches_bot_provisioning_via_policy(monkeypatch):
    from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
    from runtime.entrypoints.telegram_longpoll import _world_state_from_update

    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3().propose(_world_state_from_update(UPDATE))
    assert result.action == "bot_provisioning@v1"
    assert result.payload["op"] == "managed_event" and result.payload["user_id"] == "5001"
