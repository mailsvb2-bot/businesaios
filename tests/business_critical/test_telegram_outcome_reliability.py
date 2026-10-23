from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.entrypoints import telegram_longpoll as mod


def test_executed_event_returns_canonical_outcome(monkeypatch):
    outcome = SimpleNamespace(ok=True, decision_id="decision-1")
    monkeypatch.setattr(mod, "_world_state_from_update", lambda *a, **kw: object())
    monkeypatch.setattr(mod, "execute_runtime_decision", lambda **kw: outcome)
    monkeypatch.setattr(mod, "_append_event", lambda *a, **kw: None)
    assert mod._execute_update(
        core=object(), executor=object(), event_log=None,
        update={"update_id": 17}, transport="longpoll",
    ) is outcome


def test_failed_diagnostic_logging_does_not_interrupt_decision():
    def fail(event):
        raise RuntimeError("diagnostics unavailable")
    log = SimpleNamespace(append=fail)
    mod._append_event(log, event_type="test", payload={"update_id": 1})


def test_failed_canonical_result_is_not_silently_treated_as_success(monkeypatch):
    class StopPolling(Exception):
        pass
    outcome = SimpleNamespace(ok=False)
    calls = []
    monkeypatch.setattr(mod, "_validate_startup", lambda token: None)
    monkeypatch.setattr(mod, "_start_health_if_enabled", lambda event_log: None)
    monkeypatch.setattr(mod, "_append_event", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "_execute_update", lambda **kw: calls.append(kw["update"]["update_id"]) or outcome)
    monkeypatch.setattr(mod, "env_int", lambda key, default: default)
    monkeypatch.setattr(mod, "time", SimpleNamespace(sleep=lambda value: (_ for _ in ()).throw(StopPolling()), time=lambda: 0.0))
    response = SimpleNamespace(json={"ok": True, "result": [{"update_id": 12, "message": {"text": "/admin"}}]})
    monkeypatch.setattr(mod, "_http_json", lambda *a, **kw: response)
    with pytest.raises(StopPolling):
        mod._run_longpoll(token="example", core=object(), executor=object(), event_log=None)
    assert calls == [12]


def test_terminal_failed_update_unblocks_following_chat(monkeypatch):
    class StopPolling(BaseException):
        pass

    attempts = []
    offsets = []
    events = []
    monkeypatch.setattr(mod, "_validate_startup", lambda token: None)
    monkeypatch.setattr(mod, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(mod, "_append_event", lambda log, **kw: events.append(kw))
    monkeypatch.setattr(mod, "env_int", lambda key, default: 2 if key == "TELEGRAM_MAX_UPDATE_ATTEMPTS" else default)
    monkeypatch.setattr(mod.time, "sleep", lambda delay: None)

    def execute(**kw):
        update_id = kw["update"]["update_id"]
        attempts.append(update_id)
        return SimpleNamespace(ok=update_id == 102)

    def http(method, url, payload=None, *, timeout_s=30):
        offset = (payload or {}).get("offset", 0)
        offsets.append(offset)
        if offset > 102:
            raise StopPolling()
        return SimpleNamespace(json={"ok": True, "result": [
            u for u in ({"update_id": 101}, {"update_id": 102}) if u["update_id"] >= offset
        ]})

    monkeypatch.setattr(mod, "_http_json", http)
    monkeypatch.setattr(mod, "_execute_update", execute)
    with pytest.raises(StopPolling):
        mod._run_longpoll(token="example", core=object(), executor=object(), event_log=None)
    assert attempts == [101, 101, 102]
    assert offsets[-1] == 103
    assert any(e["event_type"] == "telegram_update_failed_terminal" for e in events)


def test_success_is_acknowledged_without_retry(monkeypatch):
    class StopPolling(BaseException):
        pass

    calls = []
    monkeypatch.setattr(mod, "_validate_startup", lambda token: None)
    monkeypatch.setattr(mod, "_start_health_if_enabled", lambda log: None)
    monkeypatch.setattr(mod, "_append_event", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "_execute_update", lambda **kw: calls.append(kw["update"]["update_id"]) or SimpleNamespace(ok=True))
    monkeypatch.setattr(mod, "_http_json", lambda *a, **kw: SimpleNamespace(json={"ok": True, "result": [{"update_id": 42}]}))
    monkeypatch.setattr(mod.time, "sleep", lambda delay: (_ for _ in ()).throw(StopPolling()))
    with pytest.raises(StopPolling):
        mod._run_longpoll(token="example", core=object(), executor=object(), event_log=None)
    assert calls == [42]
