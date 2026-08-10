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

    def _forward(self, name: str, **kwargs):
        require_effect_capability(self.token)
        return getattr(self.impl, name)(**kwargs)

    def send_message(self, **kwargs):  # type: ignore[override]
        return self._forward("send_message", **kwargs)

    def send_audio(self, **kwargs):  # type: ignore[override]
        return self._forward("send_audio", **kwargs)

    def send_weather(self, **kwargs):  # type: ignore[override]
        return self._forward("send_weather", **kwargs)

    def set_user_setting(self, **kwargs):  # type: ignore[override]
        return self._forward("set_user_setting", **kwargs)

    def log_mood(self, **kwargs):  # type: ignore[override]
        return self._forward("log_mood", **kwargs)

    def select_tariff(self, **kwargs):  # type: ignore[override]
        return self._forward("select_tariff", **kwargs)

    def capture_payment(self, **kwargs):  # type: ignore[override]
        return self._forward("capture_payment", **kwargs)

    def deploy_policy(self, **kwargs):  # type: ignore[override]
        return self._forward("deploy_policy", **kwargs)

    def rollback_policy(self, **kwargs):  # type: ignore[override]
        return self._forward("rollback_policy", **kwargs)

    def reconcile_payments(self, **kwargs):  # type: ignore[override]
        return self._forward("reconcile_payments", **kwargs)

    def grant_access(self, **kwargs):  # type: ignore[override]
        return self._forward("grant_access", **kwargs)

    def poll_telegram_updates(self, **kwargs):  # type: ignore[override]
        return self._forward("poll_telegram_updates", **kwargs)

    def track_event(self, **kwargs):  # type: ignore[override]
        return self._forward("track_event", **kwargs)

    def answer_callback_query(self, **kwargs):  # type: ignore[override]
        return self._forward("answer_callback_query", **kwargs)

    def generate_visual_creative(self, **kwargs):  # type: ignore[override]
        return self._forward("generate_visual_creative", **kwargs)

    def poll_visual_creative(self, **kwargs):  # type: ignore[override]
        return self._forward("poll_visual_creative", **kwargs)


__all__ = ["GuardedEffectsPort", "set_effect_capability", "clear_effect_capability"]
