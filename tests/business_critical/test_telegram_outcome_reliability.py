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
