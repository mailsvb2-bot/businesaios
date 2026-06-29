"""Thread-local capability gate for EffectsPort.

Goal:
  Make "direct effects" calls fail by default and succeed only while the
  RuntimeExecutor is actively executing a validated DecisionEnvelope.

This is not meant to be a cryptographic boundary (Python can't provide that),
but it strongly reduces accidental bypasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from runtime.firewall.process_guard import (
    clear_effect_capability,
    require_effect_capability,
    set_effect_capability,
)
from runtime.ports.effects import EffectsPort

@dataclass
class GuardedEffectsPort(EffectsPort):
    """EffectsPort proxy that requires an active capability token."""

    token: str
    impl: EffectsPort

    def _require(self) -> None:
        require_effect_capability(self.token)

    def send_message(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.send_message(**kwargs)

    def send_audio(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.send_audio(**kwargs)

    def send_weather(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.send_weather(**kwargs)

    def set_user_setting(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.set_user_setting(**kwargs)

    def log_mood(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.log_mood(**kwargs)

    def select_tariff(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.select_tariff(**kwargs)

    def capture_payment(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.capture_payment(**kwargs)

    def deploy_policy(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.deploy_policy(**kwargs)

    def rollback_policy(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.rollback_policy(**kwargs)


    def reconcile_payments(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.reconcile_payments(**kwargs)

    def grant_access(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.grant_access(**kwargs)

    def poll_telegram_updates(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.poll_telegram_updates(**kwargs)

    def track_event(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.track_event(**kwargs)

    def answer_callback_query(self, **kwargs):  # type: ignore[override]
        self._require()
        return self.impl.answer_callback_query(**kwargs)


__all__ = [
    "GuardedEffectsPort",
    "set_effect_capability",
    "clear_effect_capability",
]
