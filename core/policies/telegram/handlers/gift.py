from __future__ import annotations

"""Gift flow handlers (Telegram UI).

Kept separate from the main router to avoid a God-module.
"""

import secrets
import time
from typing import Callable, Optional

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.ux.callbacks import CB_GIFT_CREATE, CB_GIFT_MENU
from core.ux.telegram_keyboards import kb_gift_menu, kb_main


def handle_gift(
    ctx: TelegramCtx,
    *,
    user_id: str,
    bot_username: str,
    gift_ttl_sec: int,
    pm: Callable[..., ProposedAction],
) -> Optional[ProposedAction]:
    # Gift deep-link: /start gift_<token>
    if ctx.cmd == "/start" and isinstance(ctx.args, str) and ctx.args.startswith("gift_"):
        token = str(ctx.args[len("gift_") :]).strip()
        note = "🎁 Вам подарили полный доступ ✅\n\nДобро пожаловать!"
        return propose(
            "grant_access@v1",
            {
                "user_id": user_id,
                "full_access": True,
                "notify_text": note,
                "notify_reply_markup": kb_main(is_admin=ctx.is_admin),
                "track_event_type": "gift_redeemed",
                "track_payload": {"token": token},
            },
        )

    if ctx.callback_data == CB_GIFT_MENU:
        msg = (
            "🎁 Подарить\n\n"
            "Нажми кнопку ниже — я создам одноразовую подарочную ссылку.\n"
            "Человек откроет её через /start и получит полный доступ."
        )
        return pm(text=msg, reply_markup=kb_gift_menu())

    if ctx.callback_data == CB_GIFT_CREATE:
        bot = (str(bot_username or "")).strip().lstrip("@")
        if not bot:
            msg = (
                "🎁 Подарить\n\n"
                "Не могу создать ссылку: неизвестен username бота.\n"
                "FIX: добавь BOT_USERNAME в env/.env (без @) или запусти RUN_MODE=telegram — "
                "на старте мы берём username через getMe и заполняем BOT_USERNAME автоматически."
            )
            return pm(text=msg, reply_markup=kb_gift_menu())

        token = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
        ttl_sec = 7 * 24 * 3600
        try:
            ttl_sec = int(gift_ttl_sec) if int(gift_ttl_sec) > 0 else int(ttl_sec)
        except Exception:
            ttl_sec = 7 * 24 * 3600
        expires_ms = int(time.time() * 1000) + int(max(60, ttl_sec)) * 1000
        link = f"https://t.me/{bot}?start=gift_{token}"

        msg = (
            "🎁 Подарочная ссылка создана\n\n"
            "Скопируй и отправь человеку:\n"
            f"{link}\n\n"
            "Одноразовая: после активации перестанет работать.\n"
            "TTL по умолчанию 7 дней (env: GIFT_TTL_SEC)."
        )
        return pm(
            text=msg,
            reply_markup=kb_gift_menu(),
            track_event_type="gift_token_created",
            track_payload={"token": token, "created_by": user_id, "expires_ms": int(expires_ms)},
        )

    return None
