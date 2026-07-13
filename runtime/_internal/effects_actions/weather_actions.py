"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime.security.runtime_asserts import assert_called_from_executor


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        value = delivery.get(key)
        if isinstance(value, Mapping) and str(value.get("source") or "").strip():
            return dict(value)
    return None


class WeatherEffectsMixin:
    def send_weather(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        city: str,
    ) -> Any:
        assert_called_from_executor()
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        city_name = str(city or "").strip()
        if not tenant:
            raise RuntimeError("TENANT_ID_REQUIRED")
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if not city_name:
            raise RuntimeError("WEATHER_CITY_REQUIRED")

        ok, txt, meta = self._open_meteo_weather(city_name)
        delivery = self.send_message(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=tenant,
            user_id=user,
            text=txt,
            reply_markup=None,
            channel="telegram",
            priority="normal",
        )
        self.event_log.emit(
            event_type="weather_sent",
            source="runtime_effects",
            user_id=user,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={
                "ok": bool(ok),
                "tenant_id": tenant,
                "city": city_name,
                "meta": meta,
            },
        )
        evidence = _delivery_evidence(delivery)
        delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
        return {
            "ok": bool(ok) and delivery_ok,
            "status": "verified" if bool(ok) and delivery_ok and evidence else "failed",
            "meta": meta,
            "delivery": delivery,
            "router_evidence": evidence if bool(ok) and delivery_ok else None,
        }

    def _open_meteo_weather(self, city: str) -> tuple[bool, str, dict[str, Any]]:
        from runtime._internal.router_support import execute_effect_action_sync

        out = execute_effect_action_sync(
            self,
            EffectActionType.WEATHER_OPEN_METEO_CURRENT,
            {"city": str(city or "").strip()},
        )
        return bool(out.get("ok", False)), str(out.get("text") or ""), dict(out.get("meta") or {})
