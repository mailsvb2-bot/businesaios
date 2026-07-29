from __future__ import annotations

from typing import Any

from core.autopilot.guardrails import evaluate_stop_loss, evaluate_stop_loss_window
from core.autopilot.read_model import business_metrics_window
from core.autopilot.resolver import resolve_autopilot_contract
from core.autopilot.stop_loss import build_stop_loss_plan
from core.policies.telegram.handlers.autopilot_parts.shared import pm
from core.policies.telegram.helpers import ProposedAction, propose
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.ux.callbacks import (
    CB_AUTOPILOT_CLEAR_STOP_LOSS,
    CB_AUTOPILOT_DASHBOARD_AUTOPILOT,
    CB_AUTOPILOT_DASHBOARD_TASKS,
    CB_AUTOPILOT_DASHBOARD_TODAY,
    CB_AUTOPILOT_MENU,
)
from core.ux.telegram_keyboards import kb_autopilot_menu


def stop_loss_verdict(ctx, *, contract, logger) -> Any:
    """Evaluate stop-loss via rolling event window when available."""

    event_store = getattr(ctx, "event_store", None)
    tenant_id = normalize_tenant_id_or_unknown(
        getattr(getattr(ctx, "state", None), "tenant_id", None)
    )
    if event_store is not None:
        try:
            safety = contract.safety_policy
            days = max(
                1,
                int(getattr(safety, "stop_loss_profit_days", 1) or 1),
                int(getattr(safety, "stop_loss_cac_days", 1) or 1),
                int(getattr(safety, "stop_loss_no_conv_days", 1) or 1),
            )
            window = business_metrics_window(
                event_store,
                tenant_id=tenant_id,
                days=days,
            )
            return evaluate_stop_loss_window(contract=contract, window=window)
        except Exception:
            from core.observability.throttled_logger import exception_throttled

            exception_throttled(
                logger,
                key=f"autopilot.stop_loss_verdict|{tenant_id}",
                msg=(
                    "telegram_autopilot: failed to compute stop-loss window "
                    "from event_store"
                ),
            )

    metrics = (
        ctx.autopilot_dashboard.get("today")
        if isinstance(ctx.autopilot_dashboard, dict)
        else None
    ) or {}
    return evaluate_stop_loss(
        contract=contract,
        metrics={
            "profit_minor_today": metrics.get("profit_minor"),
            "cac_minor_today": metrics.get("cac_minor"),
        },
    )


def handle_menu_or_dashboard(
    ctx,
    *,
    user_id: str,
    sess: dict,
    sl,
    logger,
) -> ProposedAction | None:
    callback = str(ctx.callback_data or "")

    if callback == CB_AUTOPILOT_MENU:
        reply_markup = kb_autopilot_menu()
        if sl.active:
            try:
                rows = list(reply_markup.get("inline_keyboard") or [])
            except Exception:
                rows = []
            rows.insert(
                1,
                [
                    {
                        "text": "🧯 Сбросить stop-loss",
                        "callback_data": CB_AUTOPILOT_CLEAR_STOP_LOSS,
                    }
                ],
            )
            reply_markup = {"inline_keyboard": rows}
        return pm(
            user_id=user_id,
            text=(
                "🚀 Business Autopilot\n\n"
                "Одна кнопка пользы: *увеличить прибыль за 7 дней*.\n"
                "Я проведу по диагностике → выберем оффер → выберем канал → "
                "запустим → буду оптимизировать (без риска)."
                + (f"\n\n⚠️ Stop-loss активен: {sl.reason}" if sl.active else "")
            ),
            reply_markup=reply_markup,
            callback_query_id=ctx.callback_query_id,
            track_event_type="autopilot_menu_opened@v1",
            track_payload={"step": "menu"},
        )

    if callback == CB_AUTOPILOT_CLEAR_STOP_LOSS:
        from core.autopilot.stop_loss import build_clear_stop_loss_plan

        tenant_id = normalize_tenant_id_or_unknown(
            getattr(ctx.state, "tenant_id", None)
        )
        return propose(
            "set_user_setting@v1",
            build_clear_stop_loss_plan(
                tenant_id=tenant_id,
                user_id=str(user_id),
                callback_query_id=ctx.callback_query_id,
            ),
        )

    dashboard_callbacks = {
        CB_AUTOPILOT_DASHBOARD_TODAY,
        CB_AUTOPILOT_DASHBOARD_AUTOPILOT,
        CB_AUTOPILOT_DASHBOARD_TASKS,
    }
    if callback not in dashboard_callbacks:
        return None

    if callback == CB_AUTOPILOT_DASHBOARD_TODAY:
        metrics = (
            ctx.autopilot_dashboard.get("today")
            if isinstance(ctx.autopilot_dashboard, dict)
            else None
        ) or {
            "leads": 0,
            "purchases": 0,
            "revenue_minor": 0,
            "profit_minor": 0,
            "cac_minor": 0,
        }
        if not sl.active:
            try:
                tenant_id = normalize_tenant_id_or_unknown(
                    getattr(ctx.state, "tenant_id", None)
                )
                contract = resolve_autopilot_contract(
                    product=getattr(ctx.state, "product", {}) or {},
                    tenant_id=tenant_id,
                )
                verdict = stop_loss_verdict(ctx, contract=contract, logger=logger)
            except Exception:
                verdict = None
            if verdict is not None and not verdict.allow:
                return propose(
                    "set_user_setting@v1",
                    build_stop_loss_plan(
                        tenant_id=tenant_id,
                        user_id=str(user_id),
                        verdict=verdict,
                        existing=sl,
                        now_ms=int(getattr(ctx.state, "timestamp_ms", 0) or 0),
                        callback_query_id=ctx.callback_query_id,
                    ),
                )
        from core.money import format_minor

        text = (
            "📊 Сегодня\n\n"
            f"Лиды: {metrics['leads']}\n"
            f"Продажи: {metrics['purchases']}\n"
            f"Выручка: {format_minor(int(metrics.get('revenue_minor') or 0), currency='RUB')}\n"
            f"Прибыль: {format_minor(int(metrics.get('profit_minor') or 0), currency='RUB')}\n"
            + (
                f"CAC: {metrics['cac_minor']} minor\n"
                if int(metrics.get("cac_minor") or 0)
                else ""
            )
        )
        return pm(
            user_id=user_id,
            text=text,
            reply_markup=kb_autopilot_menu(),
            callback_query_id=ctx.callback_query_id,
        )

    if callback == CB_AUTOPILOT_DASHBOARD_AUTOPILOT:
        items = (
            ctx.autopilot_dashboard.get("actions_7d")
            if isinstance(ctx.autopilot_dashboard, dict)
            else None
        ) or []
        if not items:
            text = "🤖 Автопилот пока не делал изменений. Запусти сценарий на 7 дней."
        else:
            lines = ["🤖 Что сделал автопилот (7 дней):\n"]
            for item in items[:10]:
                lines.append(
                    f"- {item.get('kind', '')} / {item.get('reason', '')}: "
                    f"{item.get('changes', {})}"
                )
            text = "\n".join(lines)
        return pm(
            user_id=user_id,
            text=text,
            reply_markup=kb_autopilot_menu(),
            callback_query_id=ctx.callback_query_id,
        )

    tasks = list(
        (sess.get("tasks") or []) if isinstance(sess.get("tasks"), list) else []
    )
    if not tasks:
        text = "✅ Нет задач. Запусти сценарий или заполни диагностику."
    else:
        lines = ["✅ Что делать тебе сегодня:"]
        for task in tasks[:3]:
            if isinstance(task, dict):
                lines.append(
                    f"- {task.get('title', '')}: {task.get('details', '')}"
                )
        text = "\n".join(lines)
    return pm(
        user_id=user_id,
        text=text,
        reply_markup=kb_autopilot_menu(),
        callback_query_id=ctx.callback_query_id,
    )
