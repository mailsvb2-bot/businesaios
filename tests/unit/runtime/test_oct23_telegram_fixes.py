"""Oct 23: repeat /start and repeat button taps must deliver; poison updates must not block polling."""
from __future__ import annotations

import pytest

from runtime._internal.effect_payloads import normalize_effect_payload
from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_clients.telegram_client import TelegramClient
from runtime.platform.delivery_state import DeliveryState


class _Http:
    def __init__(self):
        self.calls = []

    def __call__(self, *, url, payload, timeout_s):
        self.calls.append(dict(payload))
        return {"ok": True, "result": {"message_id": len(self.calls)}}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:t")
    c = TelegramClient(delivery_state=DeliveryState(db_path=tmp_path / "d.db"))
    http = _Http()
    monkeypatch.setattr(c, "_http_post", http)
    return c, http


def test_same_menu_text_in_new_decisions_is_sent_every_time(client):
    c, http = client
    for scope in ("decision-1", "decision-2", "decision-3"):
        ok, meta = c.send_message(chat_id="4001", text="🏠 ClientPlatform", delivery_scope=scope)
        assert ok and meta["mode"] == "direct"
    assert len(http.calls) == 3


def test_replay_of_the_same_decision_is_still_deduplicated(client):
    c, http = client
    c.send_message(chat_id="4001", text="menu", delivery_scope="decision-1")
    ok, meta = c.send_message(chat_id="4001", text="menu", delivery_scope="decision-1")
    assert ok and meta["mode"] == "dedup"
    assert len(http.calls) == 1


def test_effect_payload_carries_delivery_scope():
    out = normalize_effect_payload(EffectActionType.TELEGRAM_SEND_MESSAGE, {"chat_id": "1", "text": "x", "delivery_scope": "k"})
    assert out["delivery_scope"] == "k"
    assert normalize_effect_payload(EffectActionType.TELEGRAM_SEND_MESSAGE, {"chat_id": "1", "text": "x"})["delivery_scope"] is None


def test_callback_pre_send_answers_without_extra_chat_action_round_trip():
    from types import SimpleNamespace

    from runtime._internal.effects_actions.telegram.messaging_parts.transport import telegram_pre_send

    calls = []
    fx = SimpleNamespace(event_log=None, _telegram_answer_callback=lambda *a, **k: calls.append("answer"),
                         _telegram_send_chat_action=lambda **k: calls.append("typing"))
    msg = SimpleNamespace(callback_query_id="cb-1", user_id="4001", decision_id="d", correlation_id="c")
    telegram_pre_send(fx, msg=msg)
    assert calls == ["answer"]


class _Stop(BaseException):
    pass


def test_poison_update_is_dropped_after_bounded_attempts(monkeypatch):
    import runtime.entrypoints.telegram_longpoll as lp

    polls = {"n": 0}
    executed = []

    def fake_http(method, url, payload=None, *, timeout_s=None):
        polls["n"] += 1
        if polls["n"] > 6:
            raise _Stop()
        offset = int((payload or {}).get("offset") or 0)
        updates = [u for u in ({"update_id": 1, "poison": True}, {"update_id": 2}) if u["update_id"] >= offset]
        return {"ok": True, "result": updates}

    def fake_execute(*, update, **_):
        executed.append(update["update_id"])
        if update.get("poison"):
            raise RuntimeError("boom")

    monkeypatch.setattr(lp, "_validate_startup", lambda token: None)
    monkeypatch.setattr(lp, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(lp, "_http_json", fake_http)
    monkeypatch.setattr(lp, "_response_payload", lambda r: r)
    monkeypatch.setattr(lp, "_execute_update", fake_execute)
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    monkeypatch.setenv("TELEGRAM_MAX_UPDATE_ATTEMPTS", "3")
    with pytest.raises(_Stop):
        lp._run_longpoll(token="t", core=None, executor=None, event_log=None)
    assert executed.count(1) == 3
    assert 2 in executed
