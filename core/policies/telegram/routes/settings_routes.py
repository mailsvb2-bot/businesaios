from __future__ import annotations

import re

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.callbacks import CB_SETTINGS_MENU, CB_SETTINGS_STATE
from core.ux.telegram_keyboards import kb_mood_rate, kb_settings_menu, kb_state_menu


def handle_settings_routes(ctx: TelegramCtx, *, user_id: str, bot_username: str, pm) -> ProposedAction | None:
    if ctx.callback_data == CB_SETTINGS_MENU:
        return pm(
            text=(
                "🧠 Настройки\n\n"
                f"Город для погоды: {ctx.city}\n\n"
                "Выбери пункт ниже."
            ),
            reply_markup=kb_settings_menu(),
        )
    if ctx.callback_data in {CB_SETTINGS_STATE, "settings:state"}:
        return pm(text="📈 Состояния", reply_markup=kb_state_menu())
    if ctx.callback_data == "settings:time:work":
        return pm(
            text=(
                "⏰ Время: утро\n\n"
                "Задай время командой: /time_work HH:MM\n"
                "Пример: /time_work 08:30"
            ),
            reply_markup=kb_settings_menu(),
        )
    if ctx.callback_data == "settings:time:home":
        return pm(
            text=(
                "🌙 Время: вечер\n\n"
                "Задай время командой: /time_home HH:MM\n"
                "Пример: /time_home 19:10"
            ),
            reply_markup=kb_settings_menu(),
        )
    if ctx.cmd in {"/time_work", "/time_home"}:
        hhmm = (ctx.args or "").strip()
        if not re.match(r"^\d{1,2}:\d{2}$", hhmm or ""):
            return pm(text="Формат времени: HH:MM (например 08:30)", reply_markup=kb_settings_menu())
        key = "time_work" if ctx.cmd == "/time_work" else "time_home"
        return propose(
            "set_user_setting@v1",
            {
                "user_id": user_id,
                "key": key,
                "value": hhmm,
                "notify_text": f"✅ Сохранено: {key} = {hhmm}",
                "callback_query_id": ctx.callback_query_id,
                "notify_reply_markup": kb_settings_menu(),
            },
        )
    if ctx.callback_data == "settings:ref":
        bot = (str(bot_username or "")).strip().lstrip("@")
        if not bot:
            msg = (
                "🔗 Реферальная ссылка\n\n"
                "Пока не могу собрать ссылку: неизвестен username бота.\n"
                "FIX: добавь BOT_USERNAME в env/.env (без @) или запусти RUN_MODE=telegram — "
                "на старте мы берём username через getMe и заполняем BOT_USERNAME автоматически."
            )
            return pm(text=msg, reply_markup=kb_settings_menu())
        return pm(
            text=(
                "🔗 Реферальная ссылка\n\n"
                "Скопируй и отправь другу:\n"
                f"https://t.me/{bot}?start=ref_{user_id}"
            ),
            reply_markup=kb_settings_menu(),
        )
    if ctx.callback_data == "state:rate":
        return pm(text="⭐ Оцени состояние (0..10)", reply_markup=kb_mood_rate())
    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("state:rate:"):
        try:
            score = int(str(ctx.callback_data).split(":")[-1])
        except Exception:
            score = 0
        score = max(0, min(10, score))
        return propose(
            "log_mood@v1",
            {
                "user_id": user_id,
                "score": int(score),
                "note": "",
                "notify_text": f"✅ Записал состояние: {score}/10",
                "callback_query_id": ctx.callback_query_id,
                "notify_reply_markup": kb_state_menu(),
            },
        )
    if ctx.callback_data in {"state:today", "state:yesterday", "state:all"}:
        if not ctx.moods:
            return pm(text="Пока нет отмеченных состояний.", reply_markup=kb_state_menu())
        title = {"state:today": "Сегодня", "state:yesterday": "Вчера", "state:all": "Последние"}.get(ctx.callback_data, "Последние")
        lines = [f"📈 Состояния: {title}\n"]
        for mood in ctx.moods:
            try:
                ts = str(mood.get("ts") or "")
                score = mood.get("score")
                note = str(mood.get("note") or "").strip()
                lines.append(f"• {ts}: {score} {(('— ' + note) if note else '')}")
            except Exception:
                continue
        return pm(text="\n".join(lines), reply_markup=kb_state_menu())
    return None
