from __future__ import annotations

"""Inline keyboard builders (UI primitives).

Why here:
- These helpers are pure data-shaping for Telegram reply_markup.
- Offers layer may need them, but offers MUST NOT depend on policies.
- Keeping them in core.ux prevents cross-layer cycles.
"""

from typing import Any, Dict, List


def inline_button(text: str, callback_data: str) -> dict[str, Any]:
    return {"text": str(text), "callback_data": str(callback_data)}


def inline_keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Telegram Bot API reply_markup for inline keyboard."""
    return {"inline_keyboard": rows}
