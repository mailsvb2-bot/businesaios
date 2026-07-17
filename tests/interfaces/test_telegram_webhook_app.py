from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from core.ai import set_decision_core_singleton
from runtime.boot.telegram_webhook_runner import create_telegram_webhook_app


class _Core:
    def issue(self, world_state):
        return SimpleNamespace(
            decision=SimpleNamespace(
                decision_id="telegram-webhook-decision",
                correlation_id="telegram-webhook-correlation",
                action="noop@v1",
                payload={"world_state": world_state},
            )
        )


class _Executor:
    def execute(self, envelope):
        return {"ok": True, "envelope": envelope}


class _EventLog:
    def emit(self, *args, **kwargs):
        return None


def _build_app():
    core = _Core()
    set_decision_core_singleton(core)
    return create_telegram_webhook_app(
        core=core,
        executor=_Executor(),
        event_store=object(),
        event_log=_EventLog(),
        payment_outbox=object(),
        learning_job=object(),
    )


def _configure_webhook(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_AUTO_REGISTER", "0")


def test_telegram_webhook_app_rejects_invalid_secret(monkeypatch):
    _configure_webhook(monkeypatch)
    client = TestClient(_build_app())

    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
    )

    assert response.status_code == 401


def test_telegram_webhook_app_accepts_valid_secret(monkeypatch):
    _configure_webhook(monkeypatch)
    client = TestClient(_build_app())

    response = client.post(
        "/telegram/webhook",
        headers={
            "X-Telegram-Bot-Api-Secret-Token": "super-secret"
        },
        json={
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1,
                "chat": {"id": 1, "type": "private"},
                "text": "/start",
                "from": {
                    "id": 1,
                    "is_bot": False,
                    "first_name": "Test",
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
