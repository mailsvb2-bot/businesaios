"""AI CEO telegram handler (pure).

Adds a user command /ceo to show a CEO plan, and callbacks to execute it.

Routing contract:
- /ceo -> ai_ceo_plan@v1
- callback ceo:plan -> ai_ceo_plan@v1
- callback ceo:run  -> explicit review; no unsigned multi-step execution
"""

from __future__ import annotations

from typing import Any

from core.ai_ceo import autonomy_from_env, build_plan, read_growth_snapshot, render_plan_text
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose, propose_message
from core.ux.callbacks import CB_CEO_MENU, CB_CEO_PLAN, CB_CEO_RUN
from core.ux.telegram_keyboards import kb_ai_ceo_menu


def handle_ai_ceo(ctx: TelegramCtx, *, user_id: str, event_store: Any | None = None) -> ProposedAction | None:
    # entrypoints: command or callbacks
    if ctx.cmd == "/ceo":
        return _propose_plan(ctx, user_id=user_id, event_store=event_store)
    if str(ctx.callback_data or "") in {CB_CEO_MENU, CB_CEO_PLAN}:
        return _propose_plan(ctx, user_id=user_id, event_store=event_store)
    if str(ctx.callback_data or "") == CB_CEO_RUN:
        # A multi-step CEO plan must be reissued as independently authorized,
        # signed decisions. The builtin execute_plan only accepts noop steps;
        # never claim a plan was executed when the canonical gate blocks it.
        return propose_message(
            user_id=user_id,
            text=(
                "🛡 Проверка запуска AI CEO\n\n"
                "План подготовлен, но автоматическое выполнение нескольких "
                "действий недоступно без отдельных подтверждённых решений "
                "DecisionCore. Ничего не запущено и бюджет не расходован.\n\n"
                "Откройте план для проверки и последующего согласования."
            ),
            reply_markup={"inline_keyboard": [[
                {"text": "📋 Проверить план", "callback_data": CB_CEO_PLAN},
            ], [
                {"text": "⬅️ В меню", "callback_data": CB_CEO_MENU},
            ]]},
            callback_query_id=ctx.callback_query_id,
        )
    return None


def _has_kpi(ctx: TelegramCtx, event_store: Any | None) -> bool:
    dash = ctx.autopilot_dashboard if isinstance(ctx.autopilot_dashboard, dict) else {}
    return event_store is not None or isinstance(dash.get("growth"), dict)


def _build(ctx: TelegramCtx, *, event_store: Any | None) -> Any:
    tenant_id = str(getattr(ctx.state, "tenant_id", "") or "")
    autonomy = autonomy_from_env()
    from core.ai_ceo.ledger import GrowthSnapshotV1
    if event_store is not None:
        snapshot = read_growth_snapshot(event_store, tenant_id=tenant_id)
    else:  # canonical read model hydrated into the policy context (user_bundle.autopilot_dashboard.growth)
        dash = ctx.autopilot_dashboard if isinstance(ctx.autopilot_dashboard, dict) else {}
        growth = dash.get("growth") if isinstance(dash.get("growth"), dict) else None
        keys = ("leads", "spend_minor", "revenue_minor", "profit_minor")
        try:
            snapshot = GrowthSnapshotV1(**{k: int(growth.get(k) or 0) for k in keys}) if growth else None
        except (TypeError, ValueError):
            snapshot = None
    if snapshot is None:
        snapshot = GrowthSnapshotV1()
    product = getattr(ctx.state, "product", {}) or {}
    return build_plan(state=ctx.state, snapshot=snapshot, autonomy=autonomy, bot_username=str(product.get("bot_username") or "") if isinstance(product, dict) else "")


def _propose_plan(ctx: TelegramCtx, *, user_id: str, event_store: Any | None) -> ProposedAction:
    plan = _build(ctx, event_store=event_store)
    text = render_plan_text(plan, has_kpi=_has_kpi(ctx, event_store))
    return propose(
        "ai_ceo_plan@v1",
        {
            "user_id": user_id,
            "text": text,
            "reply_markup": kb_ai_ceo_menu(can_run=has_permission(ctx, "business_manage")),
            "callback_query_id": ctx.callback_query_id,
            "track_event_type": "ai_ceo_plan_shown" + "@v1",
            "track_payload": {"plan_id": plan.plan_id},
        },
    )
