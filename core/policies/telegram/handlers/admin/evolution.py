from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def handle_evolution(ctx: TelegramCtx, *, user_id: str, has_perm, pm) -> ProposedAction | None:
    if ctx.callback_data == "admin:evolution:regen_copy":
        if not ctx.is_admin or not has_perm(ctx, "admin:evolution:regen_copy"):
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        kb = {
            "inline_keyboard": [
                [{"text": "🧬 nudge", "callback_data": "admin:evolution:regen_copy:nudge"}],
                [{"text": "🧬 post_launch", "callback_data": "admin:evolution:regen_copy:post_launch"}],
                [{"text": "🧬 offer", "callback_data": "admin:evolution:regen_copy:offer"}],
                [{"text": "🧬 offer_nextday", "callback_data": "admin:evolution:regen_copy:offer_nextday"}],
                [{"text": "🧬 deadline", "callback_data": "admin:evolution:regen_copy:deadline"}],
                [{"text": "🧬 lastcall", "callback_data": "admin:evolution:regen_copy:lastcall"}],
                [{"text": "⬅️ Назад", "callback_data": "admin:menu"}],
            ]
        }
        return pm(
            text=(
                "🧬 Эволюция: регенерация копирайта (slow loop)\n\n"
                "Это НЕ выполняет set_marketing_copy в runtime.\n"
                "Мы лишь ставим job в outbox через enqueue_evolution_job@v1.\n"
                "Дальше отдельный evolution worker обрабатывает job и пишет события в event-store.\n\n"
                "Выбери шаг автоворонки:"
            ),
            reply_markup=kb,
        )

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:evolution:regen_copy:"):
        if not ctx.is_admin or not has_perm(ctx, "admin:evolution:regen_copy"):
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        step_key = str(ctx.callback_data).split(":", 3)[-1].strip()
        notify = (
            "✅ Job поставлен в очередь эволюции.\n\n"
            f"Шаг: {step_key}\n"
            "Worker выполнит regenerate_marketing_copy и запишет событие в event store."
        )
        return propose(
            "enqueue_evolution_job@v1",
            {
                "user_id": user_id,
                "job_kind": "regenerate_marketing_copy",
                "payload": {
                    "step_key": step_key,
                    "admin_id": user_id,
                    "chat_id": ctx.chat_id,
                    "notify_text": notify,
                    "notify_reply_markup": kb_staff_menu(),
                    "callback_query_id": ctx.callback_query_id,
                },
            },
        )
    return None
