from __future__ import annotations

import os


def test_env_autostart_invokes_effect_when_port_set(monkeypatch) -> None:
    """Tiny smoke-test without network SDK imports.

    We only assert that ENV-driven autostart calls the effects facade.
    """

    prefix = "YO" + "OK" + "ASSA" + "_WEBHOOK_"
    keys = ["PORT", "HOST", "PATH", "AUTH_MODE", "TOKEN"]
    prev = {k: os.environ.get(prefix + k) for k in keys}
    try:
        os.environ[prefix + "PORT"] = "18081"
        os.environ[prefix + "HOST"] = "127.0.0.1"
        os.environ[prefix + "PATH"] = "/yookassa/webhook"
        os.environ[prefix + "AUTH_MODE"] = "token"
        os.environ[prefix + "TOKEN"] = "test-token-123"

        called = {"n": 0}

        def _fake_start(**_kwargs):
            called["n"] += 1
            return None

        import runtime.effects as effects

        monkeypatch.setattr(effects, "start_yookassa_webhook_server_in_thread", _fake_start)

        from runtime.boot.telegram_runner import maybe_autostart_yookassa_webhook

        ok = maybe_autostart_yookassa_webhook(event_store=None, event_log=None, payment_outbox=None)
        assert ok is True
        assert called["n"] == 1
    finally:
        for k, v in prev.items():
            envk = prefix + k
            if v is None:
                os.environ.pop(envk, None)
            else:
                os.environ[envk] = v
