from __future__ import annotations

from types import SimpleNamespace

from importlib import import_module
from runtime.executor import executor_context


class _EventLog:
    def __init__(self) -> None:
        self.events = []

    def emit(self, **kw):
        self.events.append(kw)

    def iter_events(self):
        return iter(self.events)


class _EffectsBase:
    event_log: _EventLog

    def __init__(self) -> None:
        self.event_log = _EventLog()
        self.telegram_outbound_queue = object()
        self._audio_lock = None
        self._last_audio_sent_at = {}
        self._min_audio_interval_s = 0.0
        self.delivery_state = None
        self._audio_delivery_keys = {}


PaymentsEffectsMixin = import_module("runtime._internal.effects_actions.payments_actions").PaymentsEffectsMixin


class _Payments(_EffectsBase, PaymentsEffectsMixin):
    def _yookassa_create_payment(self, **kwargs):
        return True, {"yookassa": {"id": "p1", "status": "pending"}}

    def send_message(self, **kwargs):
        self.event_log.emit(event_type="message_sent", payload=kwargs)
        return {"ok": True}


TelegramEffectsMixin = import_module("runtime._internal.effects_actions.telegram_actions").TelegramEffectsMixin


class _Telegram(_EffectsBase, TelegramEffectsMixin):
    pass


def test_capture_payment_unsupported_provider_fails_honestly():
    fx = _Payments()
    with executor_context():
        out = fx.capture_payment(
            decision_id="d1",
            correlation_id="c1",
            user_id="u1",
            amount=100,
            currency="RUB",
            provider="stripe",
            metadata=None,
        )
    assert out["ok"] is False
    assert out["meta"]["mode"] == "unsupported"


def test_answer_callback_emits_observable_event(monkeypatch):
    fx = _Telegram()

    class _Client:
        def __init__(self, outbound_queue):
            self.outbound_queue = outbound_queue

        def answer_callback_query(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        "runtime._internal.effects_clients.telegram_client.TelegramClient",
        _Client,
    )
    with executor_context():
        out = fx.answer_callback_query(
            decision_id="d1",
            correlation_id="c1",
            user_id="u1",
            callback_query_id="cb1",
            text="ok",
            show_alert=False,
        )
    assert out["ok"] is True
    assert any(e["event_type"] == "telegram_callback_answered" for e in fx.event_log.events)


def test_send_audio_uses_audio_url_contract(monkeypatch):
    fx = _Telegram()

    class _Client:
        def __init__(self, outbound_queue):
            self.outbound_queue = outbound_queue

        def send_audio(self, **kwargs):
            assert kwargs["audio_url"] == "/tmp/a.ogg"
            return True, {"sent": True}

    monkeypatch.setattr(
        "runtime._internal.effects_clients.telegram_client.TelegramClient",
        _Client,
    )
    with executor_context():
        out = fx.send_audio(
            decision_id="d1",
            correlation_id="c1",
            user_id="u1",
            path="/tmp/a.ogg",
            kind="voice",
        )
    assert out["ok"] is True
    assert any(e["event_type"] == "audio_sent" for e in fx.event_log.events)
