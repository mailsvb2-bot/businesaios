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


def test_poison_update_is_retained_and_other_update_succeeds(monkeypatch, tmp_path):
    """One poisoned update cannot starve unrelated chats or vanish on restart."""
    from types import SimpleNamespace
    import runtime.entrypoints.telegram_longpoll as lp
    import runtime.platform.telegram_inbox as inbox_mod

    monkeypatch.setattr(inbox_mod, "_get_db_path", lambda: tmp_path / "delivery.db")
    executed = []
    polls = []

    def fake_http(method, url, payload=None, *, timeout_s=None):
        offset = (payload or {}).get("offset")
        polls.append(offset)
        if len(polls) > 2:
            raise _Stop()
        updates = [{"update_id": 1, "poison": True}, {"update_id": 2}]
        return SimpleNamespace(json={"ok": True, "result": [
            update for update in updates if offset is None or update["update_id"] >= offset
        ]})

    def fake_execute(*, update, **_):
        executed.append(update["update_id"])
        if update.get("poison"):
            raise RuntimeError("boom")
        return SimpleNamespace(ok=True)

    monkeypatch.setattr(lp, "_validate_startup", lambda token: None)
    monkeypatch.setattr(lp, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(lp, "_http_json", fake_http)
    monkeypatch.setattr(lp, "_execute_update", fake_execute)
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    with pytest.raises(_Stop):
        lp._run_longpoll(token="t", core=None, executor=None, event_log=None)

    from runtime.platform.telegram_inbox import TelegramInbox
    recovered = TelegramInbox("t")
    assert recovered.cursor() == 3
    assert recovered.pending_count() == 1
    assert executed == [1, 2]
    assert polls[1] == 3
