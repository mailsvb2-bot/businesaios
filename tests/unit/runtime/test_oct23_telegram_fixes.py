"""Oct 23: repeat /start and repeat button taps must deliver; poison updates must not block polling."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.entrypoints import telegram_longpoll as lp
from runtime.platform.telegram_inbox import TelegramInbox

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

    recovered = TelegramInbox("t")
    assert recovered.cursor() == 3
    assert recovered.pending_count() == 1
    assert executed == [1, 2]
    assert polls[1] == 3



# Durable ingress: crash recovery, negative outcomes, per-bot isolation.

@pytest.fixture
def db(monkeypatch, tmp_path):
    import runtime.platform.telegram_inbox as inbox_mod
    path = tmp_path / "delivery.db"
    monkeypatch.setattr(inbox_mod, "_get_db_path", lambda: path)
    return path


def test_crash_recovery_and_scope_isolation(db):
    a = TelegramInbox("bot-A")
    a.stage([{"update_id": 21, "message": {"text": "/start"}},
             {"update_id": 22, "message": {"text": "hello"}}])
    assert a.cursor() == 23
    assert [u["update_id"] for u in TelegramInbox("bot-A").due()] == [21, 22]
    assert TelegramInbox("bot-B").due() == []
    a.complete(21)
    assert [u["update_id"] for u in TelegramInbox("bot-A").due()] == [22]
    assert a.pending_count() == 1


def test_batch_rollback_never_advances_cursor(db):
    a = TelegramInbox("bot")
    with pytest.raises(ValueError):
        a.stage([{"update_id": 7}, {"no_update_id": True}])
    assert a.cursor() is None
    assert a.pending_count() == 0


def test_failure_kept_durable_and_recovers_after_retry(db, monkeypatch):
    import runtime.platform.telegram_inbox as mod
    clock = [100.0]
    monkeypatch.setattr(mod.time, "time", lambda: clock[0])
    a = TelegramInbox("bot")
    a.stage([{"update_id": 9}])
    a.failed(9, RuntimeError("sensitive credentials must not persist"))
    assert a.pending_count() == 1
    assert a.due() == []
    clock[0] = 101.0
    assert a.due() == [{"update_id": 9}]
    a.complete(9)
    assert TelegramInbox("bot").pending_count() == 0


class StopPolling(BaseException):
    pass


def test_unconfirmed_outcome_is_not_dropped_on_poll_and_recovers(db, monkeypatch):
    import runtime.platform.telegram_inbox as mod
    monkeypatch.setattr(lp, "_validate_startup", lambda token: None)
    monkeypatch.setattr(lp, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(lp, "_append_event", lambda *a, **kw: None)
    monkeypatch.setattr(lp.time, "sleep", lambda delay: None)
    seen = []
    def execute(**kw):
        seen.append(kw["update"]["update_id"])
        return SimpleNamespace(ok=False)
    monkeypatch.setattr(lp, "_execute_update", execute)
    calls = []
    def poll(method, url, payload=None, *, timeout_s=30):
        calls.append(dict(payload or {}))
        if len(calls) == 2:
            raise StopPolling()
        return SimpleNamespace(json={"ok": True, "result": [{"update_id": 42}]})
    monkeypatch.setattr(lp, "_http_json", poll)
    with pytest.raises(StopPolling):
        lp._run_longpoll(token="bot", core=None, executor=None, event_log=None)
    assert seen == [42]
    assert TelegramInbox("bot").pending_count() == 1
    assert calls[1]["offset"] == 43
    monkeypatch.setattr(lp, "_execute_update", lambda **kw: SimpleNamespace(ok=True))
    recovered = TelegramInbox("bot")
    # The original backoff has passed after the simulated clock moves.
    monkeypatch.setattr(mod.time, "time", lambda: 10**12)
    for update in recovered.due():
        outcome = lp._execute_update(core=None, executor=None, event_log=None,
                                     update=update, transport="longpoll")
        if outcome.ok:
            recovered.complete(update["update_id"])
    assert recovered.pending_count() == 0

def test_canonical_execution_returns_outcome(monkeypatch):
    outcome = SimpleNamespace(ok=False, decision_id="d-1")
    monkeypatch.setattr(lp, "_world_state_from_update", lambda *a, **kw: object())
    monkeypatch.setattr(lp, "execute_runtime_decision", lambda **kw: outcome)
    monkeypatch.setattr(lp, "_append_event", lambda *a, **kw: None)
    assert lp._execute_update(core=None, executor=None, event_log=None,
                              update={"update_id": 17}, transport="longpoll") is outcome


def test_diagnostic_failure_does_not_abort_delivery():
    log = SimpleNamespace(append=lambda event: (_ for _ in ()).throw(OSError("log unavailable")))
    lp._append_event(log, event_type="telegram_test", payload={"update_id": 17})


def _proposed_actions(path: str) -> set[str]:
    tree = ast.parse((Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8"))
    actions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "propose" and node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                actions.add(node.args[0].value)
    return actions


def test_autopilot_launch_never_issues_unsigned_composite_plan():
    actions = _proposed_actions("core/policies/telegram/handlers/autopilot_parts/flow_launch.py")
    assert "execute_plan@v1" not in actions
    assert "set_user_setting@v1" in actions


def test_profit_sprint_callbacks_never_issue_unsigned_composite_plan():
    actions = _proposed_actions("core/policies/telegram/handlers/autopilot_parts/flow.py")
    assert "execute_plan@v1" not in actions
    assert "set_user_setting@v1" in actions
    assert "profit_sprint_onboarding_lead_source@v1" in actions


def test_production_guard_still_rejects_non_noop_inline_plan():
    from runtime.enforcement.action_contracts import validate_execute_plan_payload

    with pytest.raises(RuntimeError, match="EXECUTE_PLAN_STEP_REQUIRES_SEPARATE_DECISION_ENVELOPE"):
        validate_execute_plan_payload(
            action="execute_plan@v1",
            payload={"steps": [{"action": "send_message@v1", "action_schema_version": 1}]},
            schemas=object(),
        )
