from runtime.effects import _effects_impl

Effects = _effects_impl().Effects


class _EventLog:
    def __init__(self):
        self.events = []

    def emit(self, **payload):
        self.events.append(payload)


def test_effects_post_init_uses_canonical_runtime_state_helpers(monkeypatch):
    monkeypatch.setenv("TELEGRAM_MIN_AUDIO_INTERVAL_S", "1.5")
    effects = Effects(event_log=_EventLog(), policy_registry=object())

    assert effects._last_sent == {}
    assert effects._audio_delivery_keys == {}
    assert effects._last_audio_sent_at == {}
    assert effects._last_err_ms == {}
    assert effects._audio_lock is not None
    assert effects._min_audio_interval_s == 1.5


def test_effects_throttled_emit_err_uses_shared_helper():
    event_log = _EventLog()
    effects = Effects(event_log=event_log, policy_registry=object())

    effects._throttled_emit_err("k", event_type="runtime_error", payload={"ok": True})
    effects._throttled_emit_err("k", event_type="runtime_error", payload={"ok": False})

    assert len(event_log.events) == 1
    assert event_log.events[0]["payload"] == {"ok": True}
