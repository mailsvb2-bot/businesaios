from __future__ import annotations

from core.policies.common.telegram_keyboards import inline_button, inline_keyboard


def retention_main_kb() -> dict:
    return inline_keyboard(
        [
            [inline_button("🔔 Ping", "ret:ping")],
        ]
    )
