"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from __future__ import annotations

from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime.security.runtime_asserts import assert_called_from_executor


class WeatherEffectsMixin:
    def send_weather(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        city: str,
    ) -> Any:
        assert_called_from_executor()
        city = (city or "").strip()
        if not city:
            city = "Amsterdam"
        ok, txt, meta = self._open_meteo_weather(city)
        # Deliver as a normal message (idempotent via decision_id). The delivery
        # effect owns proof of the user-visible external action.
        delivery = self.send_message(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=str(user_id),
            text=txt,
            reply_markup=None,
            channel="telegram",
            priority="normal",
        )
        self.event_log.emit(
            event_type="weather_sent",
            source="runtime_effects",
            user_id=str(user_id),
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={"ok": bool(ok), "city": city, "meta": meta},
        )
        result = {"ok": bool(ok), "meta": meta, "delivery": delivery}
        if isinstance(delivery, dict) and isinstance(delivery.get("evidence"), dict):
            result["evidence"] = dict(delivery["evidence"])
        return result

    def _open_meteo_weather(self, city: str) -> tuple[bool, str, dict[str, Any]]:
        from runtime._internal.router_support import execute_effect_action_sync

        out = execute_effect_action_sync(
            self,
            EffectActionType.WEATHER_OPEN_METEO_CURRENT,
            {"city": str(city or "").strip()},
        )
        return bool(out.get("ok", False)), str(out.get("text") or ""), dict(out.get("meta") or {})
