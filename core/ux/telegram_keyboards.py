"""Pure Telegram keyboard facade.

This module preserves the historic import surface while delegating to focused
keyboard modules. It remains the single canonical import point for callers.
"""

from __future__ import annotations

from core.ux.keyboards.admin import kb_staff_menu
from core.ux.keyboards.autopilot import (
    kb_ads_apply_pending,
    kb_autopilot_menu,
    kb_growth_menu,
    kb_profit_sprint_lead_sources,
)
from core.ux.keyboards.main import kb_back_main, kb_main
from core.ux.keyboards.payments import kb_gift_menu, kb_pay_selected, kb_sub, kb_tariffs
from core.ux.keyboards.settings import (
    kb_demo_kind,
    kb_mood_rate,
    kb_settings_menu,
    kb_state_menu,
    kb_weather,
)

def kb_ai_ceo_menu() -> dict:
    from core.ux.telegram_keyboards_ai_ceo import kb_ai_ceo_menu as _kb_ai_ceo_menu

    return _kb_ai_ceo_menu(can_run=True)
