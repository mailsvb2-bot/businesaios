from __future__ import annotations

from fastapi.testclient import TestClient

from runtime.boot.telegram_webhook_runner import create_telegram_webhook_app


class _Core:
    def _issue_test_decision(self, world_state):
        return {'ok': True, 'world_state': world_state}

    def __getattr__(self, name):
        if name == 'decide':
            return self._issue_test_decision
        raise AttributeError(name)


class _Executor:
    def execute(self, envelope):
        return {'ok': True, 'envelope': envelope}


class _EventLog:
    def emit(self, *args, **kwargs):
        return None


def test_telegram_webhook_app_rejects_invalid_secret(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123:abc')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_ENABLED', '1')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET', 'super-secret')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_PATH', '/telegram/webhook')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_AUTO_REGISTER', '0')

    app = create_telegram_webhook_app(
        core=_Core(),
        executor=_Executor(),
        event_store=object(),
        event_log=_EventLog(),
        payment_outbox=object(),
        learning_job=object(),
    )
    client = TestClient(app)
    response = client.post('/telegram/webhook', json={'update_id': 1})
    assert response.status_code == 401


def test_telegram_webhook_app_accepts_valid_secret(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123:abc')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_ENABLED', '1')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET', 'super-secret')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_PATH', '/telegram/webhook')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_AUTO_REGISTER', '0')

    app = create_telegram_webhook_app(
        core=_Core(),
        executor=_Executor(),
        event_store=object(),
        event_log=_EventLog(),
        payment_outbox=object(),
        learning_job=object(),
    )
    client = TestClient(app)
    response = client.post(
        '/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token': 'super-secret'},
        json={'update_id': 1, 'message': {'message_id': 1, 'date': 1, 'chat': {'id': 1, 'type': 'private'}, 'text': '/start', 'from': {'id': 1, 'is_bot': False, 'first_name': 'Test'}}},
    )
    assert response.status_code == 200
    assert response.json() == {'ok': True}
