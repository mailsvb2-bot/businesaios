from __future__ import annotations

from core.policies.common.telegram_keyboards import inline_button, inline_keyboard


def sales_main_kb() -> dict:
    return inline_keyboard(
        [
            [inline_button("⚡ 1‑клик польза", "sales:one_click_value")],
            [inline_button("💼 Оффер", "sales:offer")],
            [inline_button("💸 Снизить цену", "sales:price_down")],
        ]
    )
