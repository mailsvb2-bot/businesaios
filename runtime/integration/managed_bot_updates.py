"""Telegram Managed Bots ingress shape (pure): ``managed_bot`` update parsing and the opt-in poll filter.

Shared by both platform ingress paths (canonical long-poll entrypoint and the interfaces runner)
and by the polling effect, so the update shape and the allowed-updates list live in one place.
"""

from __future__ import annotations

import json
from typing import Any

from runtime.platform.config.env_flags import env_bool

SESSION_SOURCE = "managed_bot_update"

# Bot API default set (everything except chat_member / reactions) plus ``managed_bot``.
MANAGED_BOT_ALLOWED_UPDATES = (
    "message", "edited_message", "channel_post", "edited_channel_post", "callback_query", "inline_query",
    "chosen_inline_result", "shipping_query", "pre_checkout_query", "poll", "poll_answer", "my_chat_member",
    "chat_join_request", "managed_bot",
)  # fmt: skip


def parse_managed_bot_update(update: Any) -> dict[str, str] | None:
    """``{"managed_bot": ManagedBotUpdated}`` -> {user_id, bot_id, username}; None for any other shape."""
    value = update.get("managed_bot") if isinstance(update, dict) else None
    if not isinstance(value, dict):
        return None
    user, bot = value.get("user"), value.get("bot")
    if not isinstance(user, dict) or not isinstance(bot, dict) or bot.get("is_bot") is not True:
        return None
    uid, bid = str(user.get("id") or ""), str(bot.get("id") or "")
    if not uid.isdigit() or not bid.isdigit():
        return None
    return {"user_id": uid, "bot_id": bid, "username": str(bot.get("username") or "")[:64]}


def platform_allowed_updates(*, tenant: bool = False) -> list[str] | None:
    """Opt-in (TELEGRAM_MANAGED_BOTS_ENABLED) list for the platform bot; None keeps the Bot API default."""
    if tenant or not env_bool("TELEGRAM_MANAGED_BOTS_ENABLED", False):
        return None
    return list(MANAGED_BOT_ALLOWED_UPDATES)


def allowed_updates_param(*, tenant: bool = False) -> dict[str, str]:
    allowed = platform_allowed_updates(tenant=tenant)
    return {} if allowed is None else {"allowed_updates": json.dumps(allowed)}


__all__ = [
    "MANAGED_BOT_ALLOWED_UPDATES",
    "SESSION_SOURCE",
    "allowed_updates_param",
    "parse_managed_bot_update",
    "platform_allowed_updates",
]
