"""Ads apply gate (prod-safe).

Goals:
- Dry-run by default.
- Explicit user enable (policy gate) required to execute irreversible ads changes.
- Limits are checked here (small, dumb primitives).

This module is deterministic and has no network / side-effects.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

ADS_APPLY_SETTING_KEY = "ads:apply_enabled"
ADS_APPLY_ENABLED_SINCE_MS_KEY = "ads:apply_enabled_since_ms"


@dataclass(frozen=True)
class AdsApplyState:
    enabled: bool
    since_ms: int = 0

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> AdsApplyState:
        if not isinstance(settings, Mapping):
            return AdsApplyState(False)
        raw = settings.get(ADS_APPLY_SETTING_KEY)
        if isinstance(raw, Mapping):
            # The single canonical settings write keeps the flag and timestamp
            # atomic. A malformed value must never implicitly enable Ads Apply.
            enabled = raw.get("enabled") is True
            timestamp = raw.get("since_ms")
        else:
            # Read compatibility for existing persisted boolean settings.
            enabled = raw is True
            timestamp = settings.get(ADS_APPLY_ENABLED_SINCE_MS_KEY)
        since_ms = timestamp if type(timestamp) is int and timestamp >= 0 else 0
        return AdsApplyState(enabled, since_ms if enabled else 0)


def build_ads_apply_toggle_action(
    *, user_id: str, enabled: bool, callback_query_id: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """One signed settings action; no noncanonical inline effect plan."""
    if type(enabled) is not bool:
        raise ValueError("ads_apply_boolean_required")
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if current_ms < 0:
        raise ValueError("ads_apply_time_invalid")
    message = (
        "✅ Применение рекламных изменений разрешено.\n\n"
        "Глобальный операторский выключатель и лимиты продолжают действовать. "
        "Без подтверждённого плана изменения не применяются."
        if enabled else
        "🛑 Применение рекламных изменений отключено. Dry-run остаётся доступным."
    )
    payload: dict[str, Any] = {
        "user_id": str(user_id),
        "key": ADS_APPLY_SETTING_KEY,
        "value": {"enabled": enabled, "since_ms": current_ms if enabled else 0},
        "notify_text": message,
        "notify_reply_markup": {"inline_keyboard": [[
            {"text": "⬅️ Назад", "callback_data": "ads:apply:menu"},
        ]]},
    }
    if callback_query_id:
        payload["callback_query_id"] = str(callback_query_id)
    return payload


def assert_ads_apply_allowed(
    *,
    state: AdsApplyState,
    hard_env_enabled: bool,
    max_daily_budget_minor: int,
    planned_daily_budget_minor: int,
    max_changes_per_day: int,
    planned_changes: int,
) -> str | None:
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
