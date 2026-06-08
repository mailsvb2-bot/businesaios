from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main


def handle_command_routes(ctx: TelegramCtx, *, user_id: str, pm) -> ProposedAction | None:
    if ctx.cmd == "/help":
        return pm(
            text=(
                "Команды:\n"
                "• /menu — меню\n"
                "• /pay — оплата выбранного тарифа\n"
                "• /status — статус оплаты/доступа\n\n"
                "Или просто напиши сообщение — я отвечу."
            ),
            reply_markup=kb_back_main(),
        )
    if ctx.cmd == "/report":
        today = ctx.autopilot_dashboard.get("today") if isinstance(ctx.autopilot_dashboard, dict) else None
        today = today or {"leads": 0, "purchases": 0, "revenue_minor": 0}
        msg = (
            "📈 Revenue Report (quick)\n\n"
            f"Лиды: {int(today.get('leads') or 0)}\n"
            f"Покупки: {int(today.get('purchases') or 0)}\n"
            f"Выручка: {int(today.get('revenue_minor') or 0)} (minor)\n\n"
            "Команды:\n"
            "• /suggest <offer_id> <action> — подсказать diff\n"
            "• /apply_suggest <offer_id> dry|apply|rollback [action] — применить/откатить\n"
            "• /boost — запустить 7-дневный спринт"
        )
        return pm(text=msg, reply_markup=kb_back_main())
    if ctx.cmd == "/boost":
        now = datetime.now(UTC)
        key = f"revenue_sprint:{ctx.state.tenant_id}"
        try:
            state = dict((ctx.settings or {}).get(key) or {})
        except Exception:
            state = {}
        ends = state.get("ends_at_utc")
        active = False
        if isinstance(ends, str):
            try:
                active = datetime.fromisoformat(ends.replace("Z", "+00:00")).astimezone(UTC) > now
            except Exception:
                active = False
        if active:
            return pm(text="🚀 Revenue Sprint уже активен.", reply_markup=kb_back_main())
        ends_dt = now + timedelta(days=7)
        new_state = {
            "status": "active",
            "started_at_utc": now.isoformat(),
            "ends_at_utc": ends_dt.isoformat(),
            "day_index": 0,
        }
        return propose(
            "set_user_setting@v1",
            {
                "user_id": str(user_id),
                "key": key,
                "value": new_state,
                "notify_text": "🚀 Revenue Sprint запущен на 7 дней. Завтра пришлю первый отчёт.",
                "notify_reply_markup": kb_back_main(),
                "callback_query_id": ctx.callback_query_id,
            },
        )
    if ctx.cmd == "/suggest":
        parts = [p for p in (ctx.args or "").split() if p.strip()]
        offer_id = parts[0] if parts else "unknown_offer"
        action = parts[1] if len(parts) > 1 else "improve_ctr"
        return propose(
            "suggest_offer_patch@v1",
            {
                "tenant_id": str(ctx.state.tenant_id),
                "product": "organization_platform",
                "env": "prod",
                "offer_id": str(offer_id),
                "action": str(action),
                "notify_user_id": str(user_id),
                "callback_query_id": ctx.callback_query_id,
            },
        )
    if ctx.cmd == "/apply_suggest":
        parts = [p for p in (ctx.args or "").split() if p.strip()]
        offer_id = parts[0] if parts else "unknown_offer"
        mode = parts[1] if len(parts) > 1 else "dry_run"
        action = parts[2] if len(parts) > 2 else "improve_ctr"
        if action == "improve_cr":
            derived_patch = {
                "guarantee_line": "Гарантия 7 дней: не почувствуешь эффект — верну деньги.",
                "urgency_line": "Цена действует до завтра.",
            }
        elif action == "increase_impressions":
            derived_patch = {"distribution_hint": {"extra_slot_per_day": 1}}
        elif action == "double_winner":
            derived_patch = {"urgency_line": "Сегодня — лучший момент начать."}
        else:
            derived_patch = {
                "headline": "За 7 дней: заметный результат. Без риска — гарантия.",
                "subheadline": "Сразу увидишь формат и первые изменения.",
            }
        return propose(
            "apply_offer_patch@v1",
            {
                "tenant_id": str(ctx.state.tenant_id),
                "product": "organization_platform",
                "env": "prod",
                "offer_id": str(offer_id),
                "patch": dict(derived_patch),
                "mode": str(mode),
                "notify_user_id": str(user_id),
                "callback_query_id": ctx.callback_query_id,
            },
        )
    return None
