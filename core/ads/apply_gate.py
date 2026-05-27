from __future__ import annotations

"""Ads apply gate (prod-safe).

Goals:
- Dry-run by default.
- Explicit user enable (policy gate) required to execute irreversible ads changes.
- Limits are checked here (small, dumb primitives).

This module is deterministic and has no network / side-effects.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

ADS_APPLY_SETTING_KEY = "ads:apply_enabled"
ADS_APPLY_ENABLED_SINCE_MS_KEY = "ads:apply_enabled_since_ms"


@dataclass(frozen=True)
class AdsApplyState:
    enabled: bool
    since_ms: int = 0

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> "AdsApplyState":
        if not isinstance(settings, Mapping):
            return AdsApplyState(False)
        try:
            enabled = bool(settings.get(ADS_APPLY_SETTING_KEY) or False)
            since_ms = int(settings.get(ADS_APPLY_ENABLED_SINCE_MS_KEY) or 0)
            return AdsApplyState(enabled, since_ms)
        except Exception:
            return AdsApplyState(False)


def build_enable_ads_apply_plan(*, user_id: str, callback_query_id: Optional[str] = None) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    steps = [
        {
            "action": "set_user_setting@v1",
            "payload": {"user_id": str(user_id), "key": ADS_APPLY_SETTING_KEY, "value": True},
        },
        {
            "action": "set_user_setting@v1",
            "payload": {"user_id": str(user_id), "key": ADS_APPLY_ENABLED_SINCE_MS_KEY, "value": int(now_ms)},
        },
        {
            "action": "emit_event@v1",
            "payload": {
                "user_id": str(user_id),
                "event_type": "ads_apply_enabled@v1",
                "payload": {"since_ms": int(now_ms)},
                "source": "ads",
            },
        },
        {
            "action": "send_message@v1",
            "payload": {
                "user_id": str(user_id),
                "text": "✅ Применение рекламных изменений разрешено.\n\nПо умолчанию всё равно используется dry-run, пока не появится конкретный план применения.",
                "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "ads:apply:menu"}]]},
                "callback_query_id": callback_query_id,
            },
        },
    ]
    return {"user_id": str(user_id), "steps": steps}


def build_disable_ads_apply_plan(*, user_id: str, callback_query_id: Optional[str] = None) -> Dict[str, Any]:
    steps = [
        {
            "action": "set_user_setting@v1",
            "payload": {"user_id": str(user_id), "key": ADS_APPLY_SETTING_KEY, "value": False},
        },
        {
            "action": "emit_event@v1",
            "payload": {"user_id": str(user_id), "event_type": "ads_apply_disabled@v1", "payload": {}, "source": "ads"},
        },
        {
            "action": "send_message@v1",
            "payload": {
                "user_id": str(user_id),
                "text": "🛑 Применение рекламных изменений отключено. (Dry-run остаётся доступным.)",
                "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "ads:apply:menu"}]]},
                "callback_query_id": callback_query_id,
            },
        },
    ]
    return {"user_id": str(user_id), "steps": steps}


def assert_ads_apply_allowed(
    *,
    state: AdsApplyState,
    hard_env_enabled: bool,
    max_daily_budget_minor: int,
    planned_daily_budget_minor: int,
    max_changes_per_day: int,
    planned_changes: int,
) -> Optional[str]:
    """Return error code if NOT allowed, else None.

    hard_env_enabled:
      global operator switch (e.g. ADS_APPLY_ENABLED=1)

    The rest are soft limits to avoid accidental overspending.
    """

    if not hard_env_enabled:
        return "ADS_APPLY_ENV_DISABLED"
    if not state.enabled:
        return "ADS_APPLY_USER_DISABLED"
    if int(max_daily_budget_minor) > 0 and int(planned_daily_budget_minor) > int(max_daily_budget_minor):
        return "ADS_APPLY_BUDGET_LIMIT"
    if int(max_changes_per_day) > 0 and int(planned_changes) > int(max_changes_per_day):
        return "ADS_APPLY_CHANGES_LIMIT"
    return None
