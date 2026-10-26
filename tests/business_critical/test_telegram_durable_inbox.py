"""Durable ingress: crash recovery, negative outcomes, per-bot isolation."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from runtime.platform.telegram_inbox import TelegramInbox
from runtime.entrypoints import telegram_longpoll as lp


@pytest.fixture
def db(monkeypatch, tmp_path):
    import runtime.platform.telegram_inbox as inbox_mod
    from runtime.platform import delivery_state
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
