"""Managed-bot onboarding/owner/finalize — fakes only, no real Telegram calls, tokens never in facts."""

from __future__ import annotations

import json
from functools import partial

import pytest

from application.business_flows import bot_provisioning as bp
from runtime._internal.effects_actions.telegram.startup import telegram_self_check_effect
from runtime.handler_impl.domains.bot_provisioning_ops import handle_bot_provisioning
from runtime.integration import managed_bot_credentials as mbc
from security.secret_vault import InMemorySecretVault

TOKEN = "777:FAKE-secret-token-value"


class FakeTelegram:
    """Records Telegram-effect calls; never touches the network."""

    def __init__(self, *, username="shop_helper_bot", bot_id=777, fail=False):
        self.username, self.bot_id, self.fail, self.calls = username, bot_id, fail, []

    def __call__(self, *, token=None, clear_webhook=False):
        self.calls.append({"token": token, "clear_webhook": clear_webhook})
        if self.fail:
            raise RuntimeError("TELEGRAM_GETME_FAILED: boom")
        return {"ok": True, "bot": {"id": self.bot_id, "is_bot": True, "username": self.username}, "webhook": None}


@pytest.fixture
def vault():
    return InMemorySecretVault()


def _run(flow, vault, tg, **kw):
    flow.effects.telegram_self_check = tg
    return flow.run(partial(handle_bot_provisioning, vault=vault, token_source=kw.pop("token_source", None)), **kw)


def _steps(flow):
    return [(e["payload"]["step"], e["payload"]["status"]) for e in flow.store.events]


def _no_token_anywhere(flow):
    blob = json.dumps([e["payload"] for e in flow.store.events]) + json.dumps([s["text"] for s in flow.effects.sent])
    assert TOKEN not in blob and "FAKE-secret" not in blob


def test_managed_onboarding_seals_token_and_finalizes(flow, vault):
    tg = FakeTelegram()
    _, text = _run(flow, vault, tg, op="managed_begin")
    assert "Создайте бота" in text
    _, text = _run(flow, vault, tg, op="managed_begin")
    assert "уже создана" in text  # idempotent per user
    _run(flow, vault, tg, op="managed_created", external_bot_id="777", username="Shop_Helper_bot")
    _, text = _run(flow, vault, tg, op="managed_complete", token_source=lambda bid: TOKEN)
    assert "подключён" in text
    assert _steps(flow) == [
        ("requested", "awaiting_bot"),
        ("bot_created", "awaiting_secret"),
        ("verified", "completed"),
    ]
    final = flow.store.events[-1]["payload"]
    assert final["credential_ref"] == "vault:managed_bot.777"
    assert tg.calls == [{"token": TOKEN, "clear_webhook": True}]
    assert mbc.resolve(final["credential_ref"], tenant_id="t1", vault=vault) == TOKEN
    assert bp.has_active_bot(bp.replay([e["payload"] for e in flow.store.events]))
    _no_token_anywhere(flow)


def test_failed_verification_rolls_back_sealed_token(flow, vault):
    tg = FakeTelegram(bot_id=999)  # identity mismatch
    _run(flow, vault, tg, op="managed_begin")
    _run(flow, vault, tg, op="managed_created", external_bot_id="777", username="shop_helper_bot")
    _, text = _run(flow, vault, tg, op="managed_complete", token_source=lambda bid: TOKEN)
    last = flow.store.events[-1]["payload"]
    assert last["status"] == "failed" and last["error_code"] == "getme_bot_id_mismatch" and last["rolled_back"]
    assert last["credential_ref"] == ""
    with pytest.raises(Exception):
        vault.get(mbc._ref("t1", "managed_bot.777"))
    _no_token_anywhere(flow)


def test_complete_refused_without_token_source_or_identity(flow, vault):
    tg = FakeTelegram()
    _run(flow, vault, tg, op="managed_begin")
    _, text = _run(flow, vault, tg, op="managed_complete", token_source=lambda bid: TOKEN)
    assert "managed_bot_identity_not_recorded" in text
    _run(flow, vault, tg, op="managed_created", external_bot_id="777", username="shop_helper_bot")
    _, text = _run(flow, vault, tg, op="managed_complete")
    assert "managed_bot_token_source_unavailable" in text and tg.calls == []


def test_stale_creation_event_rejected():
    item = bp.Provisioning("r", "", bp.ProvisioningStatus.AWAITING_BOT, created_ms=1_000_000, source="managed")
    with pytest.raises(ValueError, match="predates"):
        bp.record_created(item, external_bot_id="1", username="shop_helper_bot", event_ms=1_000_000 - 61_000)
    assert bp.record_created(item, external_bot_id="1", username="shop_helper_bot", event_ms=1_000_000 - 59_000)
    done = bp.Provisioning("r", "shop_helper_bot", bp.ProvisioningStatus.AWAITING_SECRET, external_bot_id="1")
    assert bp.record_created(done, external_bot_id="1", username="shop_helper_bot") is None
    with pytest.raises(ValueError, match="does not match"):
        bp.record_created(done, external_bot_id="2", username="shop_helper_bot")


def _connected(flow, vault, tg):
    _run(flow, vault, tg, op="managed_begin")
    _run(flow, vault, tg, op="managed_created", external_bot_id="777", username="shop_helper_bot")
    _run(flow, vault, tg, op="managed_complete", token_source=lambda bid: TOKEN)


def test_owner_disable_activate_revoke_with_rollback(flow, vault):
    tg = FakeTelegram()
    _connected(flow, vault, tg)
    _, text = _run(flow, vault, tg, op="disable")
    assert "приостановлен" in text
    tg.fail = True
    _, text = _run(flow, vault, tg, op="activate")
    assert "остаётся приостановленным" in text  # rollback: no fact written
    assert _steps(flow)[-1] == ("disable", "disabled")
    tg.fail = False
    _, text = _run(flow, vault, tg, op="activate")
    assert "снова работает" in text and _steps(flow)[-1] == ("activated", "completed")
    _, text = _run(flow, vault, tg, op="revoke")
    state = bp.replay([e["payload"] for e in flow.store.events])
    assert next(iter(state.values())).status is bp.ProvisioningStatus.REVOKED
    assert next(iter(state.values())).credential_ref == ""
    assert flow.store.events[-1]["payload"]["credential_retired"] is True
    with pytest.raises(Exception):
        vault.get(mbc._ref("t1", "managed_bot.777"))
    _, text = _run(flow, vault, tg, op="activate")
    assert "bot_provisioning_not_found" in text
    _no_token_anywhere(flow)


def test_env_and_unresolved_refs_on_classic_verify(flow, vault, monkeypatch):
    tg = FakeTelegram()
    _run(flow, vault, tg, op="request", arg="shop_helper_bot")
    _run(flow, vault, tg, op="attach", arg="vault:managed_bot.404")
    _, text = _run(flow, vault, tg, op="verify")
    assert "credential_unresolved:vault" in text and tg.calls == []
    _run(flow, vault, tg, op="cancel")
    _run(flow, vault, tg, op="request", arg="shop_helper_bot")
    monkeypatch.setenv("SHOP_BOT_TOKEN", TOKEN)
    _run(flow, vault, tg, op="attach", arg="env:SHOP_BOT_TOKEN")
    _, text = _run(flow, vault, tg, op="verify")
    assert "подключён" in text and tg.calls[-1]["clear_webhook"] is True


class FakeTransport:
    """Fake HTTP transport for the self-check effect: webhook set until deleteWebhook is called."""

    def __init__(self):
        self.webhook, self.methods = "https://old.example/hook", []

    def request(self, method, url, body=None, headers=None, timeout_s=None, **_):
        name = url.rsplit("/", 1)[-1]
        self.methods.append(name)
        if name == "getMe":
            result = {"id": 777, "is_bot": True, "username": "shop_helper_bot"}
        elif name == "getWebhookInfo":
            result = {"url": self.webhook}
        else:
            self.webhook, result = "", True
        return {"ok": True, "result": result}


def test_self_check_effect_clears_tenant_webhook_only_when_asked(monkeypatch):
    seen = []

    def fake_http(method, url, body, *, timeout_s=20, transport=None, headers=None):
        return transport.request(method, url, body, headers, timeout_s)

    import runtime._internal.effects_actions.telegram.startup as st

    monkeypatch.setattr(st, "_http_json", fake_http)
    view = type("V", (), {})()
    view.http_transport, view._telegram_startup_checked, view._telegram_me = FakeTransport(), False, None
    with pytest.raises(Exception):
        telegram_self_check_effect(view, token=TOKEN)
    assert "deleteWebhook" not in view.http_transport.methods
    out = telegram_self_check_effect(view, token=TOKEN, clear_webhook=True)
    seen.append(out)
    assert out["ok"] and view.http_transport.methods.count("deleteWebhook") == 1
