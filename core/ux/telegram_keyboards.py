from __future__ import annotations

"""Pure Telegram keyboard facade.

This module preserves the historic import surface while delegating to focused
keyboard modules. It remains the single canonical import point for callers.
"""



def kb_ai_ceo_menu() -> dict:
    from core.ux.telegram_keyboards_ai_ceo import kb_ai_ceo_menu as _kb_ai_ceo_menu

    return _kb_ai_ceo_menu(can_run=True)
