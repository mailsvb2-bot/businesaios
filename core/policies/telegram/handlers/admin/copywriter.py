from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def handle_copywriter(ctx: TelegramCtx, *, user_id: str, has_perm, pm) -> ProposedAction | None:
    if ctx.callback_data == "admin:copy:menu":
        if not ctx.is_admin or not has_perm(ctx, "admin:copy:menu"):
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        kb = {
            "inline_keyboard": [
                [{"text": "✍️ nudge", "callback_data": "admin:copy:gen:nudge"}],
                [{"text": "✍️ post_launch", "callback_data": "admin:copy:gen:post_launch"}],
                [{"text": "✍️ offer", "callback_data": "admin:copy:gen:offer"}],
                [{"text": "✍️ offer_nextday", "callback_data": "admin:copy:gen:offer_nextday"}],
                [{"text": "✍️ deadline", "callback_data": "admin:copy:gen:deadline"}],
                [{"text": "✍️ lastcall", "callback_data": "admin:copy:gen:lastcall"}],
                [{"text": "⬅️ Назад", "callback_data": "admin:menu"}],
            ]
        }
        return pm(
            text=(
                "🤖 ИИ‑копирайтер автоворонки\n\n"
                "Выбери шаг — я сгенерирую A/B варианты и сохраню их (event‑sourced).\n"
                "Дальше их можно подключить к рассылкам через governed scheduler."
            ),
            reply_markup=kb,
        )

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:copy:gen:"):
        if not ctx.is_admin or not has_perm(ctx, "admin:copy:menu"):
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        step_key = str(ctx.callback_data).split(":", 3)[-1].strip()
        from core.admin.ai_marketing import generate_copy_variants

        vv = generate_copy_variants(step_key=step_key)
        txt = (
            f"🤖 Копирайтер: {step_key}\n\n"
            f"A) {vv['a']}\n\n"
            f"B) {vv['b']}\n\n"
            "✅ Сохранено."
        )
        return propose(
            "set_marketing_copy@v1",
            {
                "admin_id": user_id,
                "step_key": step_key,
                "variant_a": vv["a"],
                "variant_b": vv["b"],
                "notify_text": txt,
                "notify_reply_markup": kb_staff_menu(),
                "callback_query_id": ctx.callback_query_id,
            },
        )
    return None
