"""Customer-bot gateway: routes from COMPLETED bots, admission, canonical poll reuse, token-scoped replies. Fakes only."""

from __future__ import annotations

import pytest

from application.business_flows import bot_gateway as gw
from application.business_flows import bot_provisioning as botprov
from runtime._internal.effects_actions import telegram_actions_polling as tap
from runtime._internal.effects_clients import bot_token_scope as bts
from runtime._internal.effects_clients.telegram_client import TelegramClient
from runtime.integration.customer_bot_gateway import CustomerBotGateway, build_customer_bot_gateway

S = botprov.ProvisioningStatus
ROUTE = gw.Route("t1", "r1", "777", "shop_bot", "vault:managed_bot.t1.r1", "5001")
ON = gw.GatewayConfig(enabled=True, max_attempts=2)


def _item(rid, status, ref="vault:x", bot="777"):
    return botprov.Provisioning(request_id=rid, username="b", status=status, credential_ref=ref, external_bot_id=bot)


def _msg(uid, text="hi", user=42):
    return {"update_id": uid, "message": {"message_id": uid, "chat": {"id": user}, "from": {"id": user, "first_name": "Ann"}, "text": text}}


def test_routes_only_completed_with_credential():
    state = {"a": _item("a", S.COMPLETED), "b": _item("b", S.DISABLED), "c": _item("c", S.REVOKED),
             "d": _item("d", S.COMPLETED, ref=""), "e": _item("e", S.VERIFYING)}  # fmt: skip
    routes = gw.active_routes(state, tenant_id="t1")
    assert [r.request_id for r in routes] == ["a"]
    assert gw.resolve_route(routes, external_bot_id=777).request_id == "a"
    assert gw.resolve_route(routes, external_bot_id="999") is None


def test_admission_dedupe_size_rate_queue():
    adm = gw.Admission(gw.GatewayConfig(per_minute_limit=2, queue_limit=10, max_payload_bytes=1024))
    assert adm.admit(ROUTE, _msg(1), now_s=0) == "admitted"
    assert adm.admit(ROUTE, _msg(1), now_s=0) == "duplicate"
    assert adm.admit(ROUTE, {"update_id": True}, now_s=0) == "rejected:update_id_required"
    assert adm.admit(ROUTE, _msg(2, "x" * 2000), now_s=0) == "rejected:payload_too_large"
    assert adm.admit(ROUTE, _msg(3), now_s=1) == "admitted"
    assert adm.admit(ROUTE, _msg(4), now_s=2) == "rejected:rate_limited"
    assert adm.admit(ROUTE, _msg(4), now_s=61) == "admitted"
    q = gw.Admission(gw.GatewayConfig(queue_limit=1))
    assert q.admit(ROUTE, _msg(1), now_s=0) == "admitted" and q.admit(ROUTE, _msg(2), now_s=0) == "rejected:queue_full"
    q.done(ROUTE)
    assert q.admit(ROUTE, _msg(2), now_s=0) == "admitted"


def test_actor_text_and_error_codes():
    assert gw.telegram_actor(_msg(1)) == (42, None, "Ann")
    assert gw.telegram_actor({"callback_query": {"from": {"id": 7, "username": "u"}}}) == (7, "u", None)
    assert gw.telegram_actor({"message": {"from": {"id": True}}}) is None
    assert gw.message_text(_msg(1, " hey ")) == "hey"
    assert gw.safe_error_code(KeyError("777:SECRET")) == "key_error"


def test_config_flag_gated_and_bounded():
    assert gw.gateway_config({}).enabled is False
    cfg = gw.gateway_config({"CUSTOMER_BOT_GATEWAY_ENABLED": "1", "CUSTOMER_BOT_GATEWAY_MAX_ATTEMPTS": "999"})
    assert cfg.enabled and cfg.max_attempts == 5
    assert build_customer_bot_gateway(event_store=object(), tenant_id="t1", dispatch=lambda *_: None, env={}) is None


class Harness:
    def __init__(self, batches, *, token="777:TOK", fail=0):
        self.batches, self.token, self.fail = list(batches), token, fail
        self.polls, self.dispatched = [], []

    def poll(self, *, token, offset, timeout_s, limit):
        self.polls.append((token, offset))
        return {"ok": True, "updates": self.batches.pop(0) if self.batches else []}

    def dispatch(self, update, route):
        self.dispatched.append((update["update_id"], bts.scoped_bot_token()))
        if self.fail:
            self.fail -= 1
            raise RuntimeError("boom 777:TOK")

    def gateway(self, config=ON):
        return CustomerBotGateway(config=config, routes=lambda: [ROUTE], resolve_token=lambda r: self.token,
                                  dispatch=self.dispatch, poll=self.poll, token_scope=bts.customer_bot_token_scope,
                                  clock=lambda: 0.0)  # fmt: skip


def test_disabled_gateway_never_polls():
    h = Harness([[_msg(1)]])
    assert h.gateway(gw.GatewayConfig()).tick() == 0 and h.polls == []


def test_tick_dispatches_inside_token_scope_and_advances_offset():
    h = Harness([[_msg(5), _msg(6)], [_msg(6)], []])
    g = h.gateway()
    assert g.tick() == 2
    assert h.dispatched == [(5, "777:TOK"), (6, "777:TOK")] and bts.scoped_bot_token() == ""
    assert g.tick() == 0 and g.stats["duplicates"] == 1
    g.tick()
    assert h.polls == [("777:TOK", None), ("777:TOK", 7), ("777:TOK", 7)]


def test_failed_update_retried_then_dead_letter_and_no_secret_in_stats():
    h = Harness([[_msg(5)], [_msg(5)], []], fail=5)
    g = h.gateway()
    assert g.tick() == 0 and g.stats["retried"] == 1
    assert h.polls[-1][1] is None
    g.tick()
    assert g.stats["dead"] == 1
    g.tick()
    assert h.polls[-1][1] == 6
    assert "TOK" not in str(g.health_snapshot())


def test_unresolved_credential_skips_poll():
    h = Harness([[_msg(1)]], token="")
    g = h.gateway()
    assert g.tick() == 0 and h.polls == [] and g.stats["last_error"] == "credential_unresolved"


def test_customer_poll_reuses_canonical_effect(monkeypatch):
    calls = []
    monkeypatch.setattr(tap, "is_telegram_mode", lambda: True)
    monkeypatch.setattr(tap, "http_json", lambda m, url, params, **_: calls.append((url, dict(params))) or {"ok": True, "result": []})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "100:PLATFORM")
    from runtime.effects import poll_customer_bot_updates

    assert poll_customer_bot_updates(token="777:TOK", offset=3)["ok"] is True
    url, params = calls[0]
    assert "bot777:TOK/getUpdates" in url and params["allowed_updates"] == "[]" and params["offset"] == 3


def test_reply_uses_scoped_customer_token_synchronously(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "100:PLATFORM")

    class NoQueue:
        def __getattr__(self, _):
            raise AssertionError("customer replies must not enter the async outbound queue")

    client = TelegramClient(outbound_queue=NoQueue(), transport=object())
    urls = []
    monkeypatch.setattr(client, "_http_post", lambda *, url, payload, timeout_s: urls.append(url) or {"ok": True, "result": {"message_id": 1}})
    with bts.customer_bot_token_scope("777:TOK"):
        ok, _ = client.send_message(chat_id="42", text="hi")
    assert ok and urls[0].endswith("/bot777:TOK/sendMessage")
    with pytest.raises(ValueError):
        with bts.customer_bot_token_scope(""):
            pass


def test_customer_update_session_cannot_forge_managed_event(monkeypatch):
    from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
    from runtime.entrypoints.telegram_longpoll import _world_state_from_update

    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "t1")
    forged = {**_msg(9, "777 shop_bot"), "managed_bot": "x"}
    state = _world_state_from_update(forged, transport="customer_bot", customer_route=ROUTE)
    assert state.session["source"] == gw.SESSION_SOURCE and state.session["customer_bot"]["bot_id"] == "777"
    result = UnifiedTelegramPolicyV3().propose(state)
    assert not (result.action == "bot_provisioning@v1" and result.payload.get("op") == "managed_event")


def test_admission_isolates_tenant_and_bot_identity():
    from dataclasses import replace

    adm = gw.Admission(gw.GatewayConfig(per_minute_limit=1, queue_limit=1))
    other_tenant = replace(ROUTE, tenant_id="t2")
    other_bot = replace(ROUTE, external_bot_id="778")
    assert adm.admit(ROUTE, _msg(10), now_s=1) == "admitted"
    assert adm.admit(other_tenant, _msg(10), now_s=1) == "admitted"
    assert adm.admit(other_bot, _msg(10), now_s=1) == "admitted"
    assert adm.admit(ROUTE, _msg(11), now_s=1) == "rejected:rate_limited"
    adm.done(ROUTE)
    assert adm.admit(other_tenant, _msg(11), now_s=1) == "rejected:rate_limited"


def test_admission_invalid_payload_and_missing_scope_fail_closed():
    from dataclasses import replace

    adm = gw.Admission(gw.GatewayConfig())
    assert adm.admit(ROUTE, {"update_id": 1, "message": {"text": object()}}, now_s=1) == "rejected:invalid_payload"
    assert adm.admit(ROUTE, _msg(1), now_s=1) == "admitted"
    assert adm.admit(replace(ROUTE, tenant_id=""), _msg(2), now_s=1) == "rejected:route_scope_required"
    assert adm.admit(replace(ROUTE, external_bot_id=""), _msg(2), now_s=1) == "rejected:route_scope_required"


def test_retry_releases_tenant_scoped_update_for_redelivery():
    h = Harness([[_msg(9)], [_msg(9)]], fail=1)
    g = h.gateway()
    assert g.tick() == 0
    assert g.stats["retried"] == 1
    assert g.tick() == 1
    assert g.stats["processed"] == 1
    assert h.dispatched == [(9, "777:TOK"), (9, "777:TOK")]
