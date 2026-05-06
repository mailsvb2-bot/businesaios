from __future__ import annotations

"""Pure Telegram keyboard facade.

This module preserves the historic import surface while delegating to focused
keyboard modules. It remains the single canonical import point for callers.
"""

from core.ux.keyboards.main import kb_main, kb_back_main
from core.ux.keyboards.autopilot import (
    kb_autopilot_menu,
    kb_profit_sprint_lead_sources,
    kb_ads_apply_pending,
    kb_growth_menu,
)
from core.ux.keyboards.settings import (
    kb_demo_kind,
    kb_weather,
    kb_settings_menu,
    kb_state_menu,
    kb_mood_rate,
)
from core.ux.keyboards.payments import kb_gift_menu, kb_tariffs, kb_sub, kb_pay_selected
from core.ux.keyboards.admin import kb_staff_menu


def kb_ai_ceo_menu() -> dict:
    from core.ux.telegram_keyboards_ai_ceo import kb_ai_ceo_menu as _kb_ai_ceo_menu

    return _kb_ai_ceo_menu(can_run=True)
