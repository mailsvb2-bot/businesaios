"""Regression: Telegram must not acknowledge an unconfirmed canonical result."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.entrypoints import telegram_longpoll as lp


class _Stop(BaseException):
    pass


def _setup(monkeypatch, tmp_path, *, outcome):
    import runtime.platform.telegram_inbox as inbox_mod
    monkeypatch.setattr(inbox_mod, "_get_db_path", lambda: tmp_path / "telegram.db")
    seen = []
    offsets = []
    monkeypatch.setattr(lp, "_validate_startup", lambda token: None)
    monkeypatch.setattr(lp, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(lp, "_append_event", lambda *a, **kw: None)
    monkeypatch.setattr(lp, "_execute_update", lambda **kw: seen.append(kw["update"]["update_id"]) or outcome)
    monkeypatch.setattr(lp, "env_int", lambda key, default: 2 if key == "TELEGRAM_MAX_UPDATE_ATTEMPTS" else default)
    monkeypatch.setattr(lp.time, "sleep", lambda delay: None)

    def poll(method, url, payload=None, *, timeout_s=30):
        offset = (payload or {}).get("offset")
        offsets.append(offset)
        if offset == 18:
            raise _Stop()
        return SimpleNamespace(json={"ok": True, "result": [{"update_id": 17}]})

    monkeypatch.setattr(lp, "_http_json", poll)
    with pytest.raises(_Stop):
        lp._run_longpoll(token="test", core=None, executor=None, event_log=None)
    return seen, offsets


def test_unconfirmed_result_is_durable_not_dropped(monkeypatch, tmp_path):
    from runtime.platform.telegram_inbox import TelegramInbox
    seen, offsets = _setup(monkeypatch, tmp_path, outcome=SimpleNamespace(ok=False))
    assert seen == [17]
    assert offsets == [None, 18]
    assert TelegramInbox("test").pending_count() == 1


def test_confirmed_result_acknowledged_once(monkeypatch, tmp_path):
    seen, offsets = _setup(monkeypatch, tmp_path, outcome=SimpleNamespace(ok=True))
    assert seen == [17]
    assert offsets == [None, 18]


def test_execution_returns_canonical_result(monkeypatch):
    outcome = SimpleNamespace(ok=False, decision_id="d-1")
    monkeypatch.setattr(lp, "_world_state_from_update", lambda *a, **kw: object())
    monkeypatch.setattr(lp, "execute_runtime_decision", lambda **kw: outcome)
    monkeypatch.setattr(lp, "_append_event", lambda *a, **kw: None)
    assert lp._execute_update(core=None, executor=None, event_log=None,
                              update={"update_id": 17}, transport="longpoll") is outcome


def test_diagnostic_failure_does_not_abort_delivery():
    log = SimpleNamespace(append=lambda event: (_ for _ in ()).throw(OSError("log unavailable")))
    lp._append_event(log, event_type="telegram_test", payload={"update_id": 17})
