from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
from core.ux.telegram_keyboards import kb_back_main

_PAID = {"succeeded", "captured", "paid"}
_PENDING = {"pending", "created", "waiting_for_capture", "processing"}
_FAILED = {"failed", "canceled", "cancelled", "rejected", "expired"}


def status_text(ctx: TelegramCtx) -> str:
    """Show product-scoped canonical payment and access projections."""
    product = getattr(ctx.state, "product", None)
    product_id = str((product if isinstance(product, dict) else {}).get("product_id") or "").strip()
    if not product_id:
        return "ℹ️ Статус оплаты недоступен: бот не привязан к продукту. Обратитесь к администратору."
    status = str(ctx.pay_status or "none").strip().lower()
    tariff = ctx.selected_tariff if isinstance(ctx.selected_tariff, dict) else {}
    title = str(tariff.get("title") or tariff.get("plan_code") or "").strip()
    lines = ["📋 Статус оплаты и доступа", ""]
    if title:
        lines.append(f"Выбранный тариф: {title}")
    if status in _PAID:
        lines.append("Оплата: ✅ получена")
    elif status in _PENDING:
        lines.append("Оплата: ⏳ ожидает подтверждения от платёжной системы")
    elif status in _FAILED:
        lines.append("Оплата: ❌ не прошла — можно оплатить заново через «Оплаты и тарифы»")
    else:
        lines.append("Оплата: платежей пока нет")
    if ctx.full_access:
        lines.append("Доступ: ✅ активирован")
    elif status in _PAID:
        lines.append("Доступ: ⏳ выдаётся автоматически после подтверждения платежа")
    else:
        lines.append("Доступ: не активирован")
    return "\n".join(lines)


def handle_command_routes(ctx: TelegramCtx, *, user_id: str, pm) -> ProposedAction | None:
    flow = handle_business_flow_routes(ctx, user_id=user_id)
    if flow is not None:
        return flow
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
    if ctx.cmd == "/status":
        return pm(text=status_text(ctx), reply_markup=kb_back_main())
    if ctx.cmd == "/privacy":
        return pm(text="🔐 Персональные данные\n\n• /export_data — показать, какие данные о вас хранятся", reply_markup=kb_back_main())
    if ctx.cmd == "/export_data":
        if (getattr(getattr(ctx, "state", None), "session", None) or {}).get("channel") not in (None, "", "telegram"):
            return pm(text="Экспорт доступен после подтверждения личности в Telegram.", reply_markup=kb_back_main())
        return propose("privacy_export@v1", {"user_id": user_id})
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


_OWNER_WORDS = {
    "меню": "/menu", "главное меню": "/menu", "статус": "/status",
    "статус оплаты": "/status", "помощь": "/help",
    "help": "/help", "menu": "/menu", "status": "/status",
}
_GOAL_VERB = re.compile(r"(хочу|хотим|нужн|надо|как\s|помоги|увелич|вырас|рост|подн|больше|снизить|улучш|привлеч)", re.I)
_GOAL_OBJECT = re.compile(r"(продаж|выручк|клиент|заказ|прибыл|конверс|лид|заявк|реклам|маркетинг|средн\w*\s+чек|бизнес|доход)", re.I)
_LEAD_SIGNAL = re.compile(
    r"(\+?\d[\d\s()-]{8,}\d|[\w.+-]+@[\w-]+\.[\w.]+|купить|куплю|цена|стоимост|"
    r"сколько стоит|тариф|подключ|заказать|записаться|оформить)", re.I,
)


def _norm(text: object) -> str:
    return " ".join(str(text or "").strip().lower().strip(".!?").split())


def classify_free_text(ctx: TelegramCtx) -> str:
    """Never confuse a verified staff request with a customer lead."""
    from core.users.roles import effective_role, has_permission

    content = str(ctx.text or "").strip()
    if ctx.cmd or ctx.callback_data or not content:
        return "none"
    if _norm(content) in _OWNER_WORDS:
        return "owner_command"
    if effective_role(is_platform_admin=bool(ctx.is_admin), roles=ctx.roles) != "guest":
        is_goal = bool(_GOAL_VERB.search(content) and _GOAL_OBJECT.search(content))
        return "business_goal" if is_goal and has_permission(ctx, "analytics") else "none"
    return "lead" if _LEAD_SIGNAL.search(content) else "customer_message"


def handle_free_text(ctx: TelegramCtx, *, user_id: str, msg: str, rerun) -> ProposedAction | None:
    kind = classify_free_text(ctx)
    if kind == "owner_command":
        return rerun(replace(ctx, cmd=_OWNER_WORDS[_norm(ctx.text)], args="", text=""))
    if kind == "business_goal":
        return propose("business_ops_summary@v1", {
            "user_id": user_id, "op": "cockpit", "arg": "cpm:growth-now",
        })
    if kind in {"customer_message", "lead"} and str(user_id or "").strip():
        reply = msg + ("\n\nЗаявка получена — с вами свяжутся." if kind == "lead" else "")
        from core.policies.telegram.context import trusted_sales_business_scope

        return propose("sales_pipeline@v1", {
            "user_id": user_id, "op": "inbound",
            "arg": str(ctx.text)[:4000], "reply": reply,
            **trusted_sales_business_scope(ctx, owner=False),
        })
    return None
