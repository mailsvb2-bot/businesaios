from __future__ import annotations

from core.ai import set_decision_core_singleton


def test_run_telegram_starts_runner(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "000:TEST")
    monkeypatch.setenv("TELEGRAM_HEALTH_PORT", "0")

    called = {"run_forever": 0}

    class _FakeRunner:
        def __init__(self, **kwargs):
            assert "decide_fn" in kwargs
            assert "execute_fn" in kwargs

        def run_forever(self):
            called["run_forever"] += 1

    import interfaces.telegram.runner as runner_mod

    monkeypatch.setattr(runner_mod, "TelegramRunner", _FakeRunner)

    from runtime.boot.telegram_runner import run_telegram

    class _Core:
        def issue(self, *_args, **_kwargs):
            raise AssertionError("issue should not be called by bootstrap")

    class _Exec:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("execute should not be called by bootstrap")

    core = _Core()
    set_decision_core_singleton(core)

    run_telegram(
        core=core,
        executor=_Exec(),
        event_log=None,
        event_store=None,
        payment_outbox=None,
        learning_job=None,
    )

    assert called["run_forever"] == 1
