from __future__ import annotations


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
        pass

    class _Exec:
        pass

    core = _Core()
    executor = _Exec()

    core.decide = lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("decide should not be called by bootstrap")
    )
    executor.execute = lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError("execute should not be called by bootstrap")
    )

    run_telegram(core=core, executor=executor, event_log=None, event_store=None, payment_outbox=None, learning_job=None)

    assert called["run_forever"] == 1
