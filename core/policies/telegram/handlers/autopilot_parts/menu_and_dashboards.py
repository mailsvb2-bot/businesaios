from __future__ import annotations

from typing import Any, Optional

from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.autopilot.resolver import resolve_autopilot_contract
from core.autopilot.read_model import business_metrics_window
from core.autopilot.guardrails import evaluate_stop_loss, evaluate_stop_loss_window
from core.autopilot.stop_loss import build_stop_loss_plan
from core.ux.callbacks import (
    CB_AUTOPILOT_MENU,
    CB_AUTOPILOT_DASHBOARD_TODAY,
    CB_AUTOPILOT_DASHBOARD_AUTOPILOT,
    CB_AUTOPILOT_DASHBOARD_TASKS,
    CB_AUTOPILOT_CLEAR_STOP_LOSS,
)
from core.ux.telegram_keyboards import kb_autopilot_menu
from core.policies.telegram.handlers.autopilot_parts.shared import pm
from core.policies.telegram.helpers import ProposedAction, propose


def stop_loss_verdict(ctx, *, contract, logger) -> Any:
    """Evaluate stop-loss via rolling event window when available, with safe fallback."""
    es = getattr(ctx, "event_store", None)
    tenant_id = normalize_tenant_id_or_unknown(getattr(getattr(ctx, "state", None), "tenant_id", None))
    if es is not None:
        try:
            s = contract.safety_policy
            days = max(
                1,
                int(getattr(s, "stop_loss_profit_days", 1) or 1),
                int(getattr(s, "stop_loss_cac_days", 1) or 1),
                int(getattr(s, "stop_loss_no_conv_days", 1) or 1),
            )
            w = business_metrics_window(es, tenant_id=tenant_id, days=days)
            return evaluate_stop_loss_window(contract=contract, window=w)
        except Exception:
            from core.observability.throttled_logger import exception_throttled

            exception_throttled(
                logger,
                key=f"autopilot.stop_loss_verdict|{tenant_id}",
                msg="telegram_autopilot: failed to compute stop-loss window from event_store",
            )

    m = (ctx.autopilot_dashboard.get("today") if isinstance(ctx.autopilot_dashboard, dict) else None) or {}
    return evaluate_stop_loss(contract=contract, metrics={"profit_minor_today": m.get("profit_minor"), "cac_minor_today": m.get("cac_minor")})


def handle_menu_or_dashboard(ctx, *, user_id: str, sess: dict, sl, logger) -> Optional[ProposedAction]:
    cb = str(ctx.callback_data or "")

    if cb == CB_AUTOPILOT_MENU:
        rm = kb_autopilot_menu()
        if sl.active:
            try:
                rows = list(rm.get("inline_keyboard") or [])
            except Exception:
                rows = []
            rows.insert(1, [{"text": "🧯 Сбросить stop-loss", "callback_data": CB_AUTOPILOT_CLEAR_STOP_LOSS}])
            rm = {"inline_keyboard": rows}
        return pm(
            user_id=user_id,
            text=(
                "🚀 Business Autopilot\n\n"
                "Одна кнопка пользы: *увеличить прибыль за 7 дней*.\n"
                "Я проведу по диагностике → выберем оффер → выберем канал → запустим → буду оптимизировать (без риска)."
                + (f"\n\n⚠️ Stop-loss активен: {sl.reason}" if sl.active else "")
            ),
            reply_markup=rm,
            callback_query_id=ctx.callback_query_id,
            track_event_type="autopilot_menu_opened" + "@v1",
            track_payload={"step": "menu"},
        )

    if cb == CB_AUTOPILOT_CLEAR_STOP_LOSS:
        from core.autopilot.stop_loss import build_clear_stop_loss_plan

        return propose("execute_plan@v1", build_clear_stop_loss_plan(user_id=str(user_id), callback_query_id=ctx.callback_query_id))

    if cb not in {CB_AUTOPILOT_DASHBOARD_TODAY, CB_AUTOPILOT_DASHBOARD_AUTOPILOT, CB_AUTOPILOT_DASHBOARD_TASKS}:
        return None

    if cb == CB_AUTOPILOT_DASHBOARD_TODAY:
        m = (ctx.autopilot_dashboard.get("today") if isinstance(ctx.autopilot_dashboard, dict) else None) or {"leads": 0, "purchases": 0, "revenue_minor": 0, "profit_minor": 0, "cac_minor": 0}
        if not sl.active:
            try:
                tenant_id = normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None))
                contract = resolve_autopilot_contract(product=getattr(ctx.state, "product", {}) or {}, tenant_id=tenant_id)
                verdict_w = stop_loss_verdict(ctx, contract=contract, logger=logger)
            except Exception:
                verdict_w = None
            if verdict_w is not None and (not verdict_w.allow):
                sp = dict(sess) if isinstance(sess, dict) else {}
                if str(sp.get("stage") or "") == "running":
                    sp["stage"] = "audit:stop_loss"
                return propose(
                    "execute_plan@v1",
                    build_stop_loss_plan(
                        user_id=str(user_id),
                        verdict=verdict_w,
                        existing=sl,
                        session_patch=sp if sp else None,
                        callback_query_id=ctx.callback_query_id,
                    ),
                )
        from core.money import format_minor

        txt = (
            "📊 Сегодня\n\n"
            f"Лиды: {m['leads']}\n"
            f"Продажи: {m['purchases']}\n"
            f"Выручка: {format_minor(int(m.get('revenue_minor') or 0), currency='RUB')}\n"
            f"Прибыль: {format_minor(int(m.get('profit_minor') or 0), currency='RUB')}\n"
            + (f"CAC: {m['cac_minor']} minor\n" if int(m.get("cac_minor") or 0) else "")
        )
        return pm(user_id=user_id, text=txt, reply_markup=kb_autopilot_menu(), callback_query_id=ctx.callback_query_id)

    if cb == CB_AUTOPILOT_DASHBOARD_AUTOPILOT:
        items = (ctx.autopilot_dashboard.get("actions_7d") if isinstance(ctx.autopilot_dashboard, dict) else None) or []
        if not items:
            txt = "🤖 Автопилот пока не делал изменений. Запусти сценарий на 7 дней."
        else:
            lines = ["🤖 Что сделал автопилот (7 дней):\n"]
            for it in items[:10]:
                lines.append(f"- {it.get('kind','')} / {it.get('reason','')}: {it.get('changes',{})}")
            txt = "\n".join(lines)
        return pm(user_id=user_id, text=txt, reply_markup=kb_autopilot_menu(), callback_query_id=ctx.callback_query_id)

    tasks = list((sess.get("tasks") or []) if isinstance(sess.get("tasks"), list) else [])
    if not tasks:
        txt = "✅ Нет задач. Запусти сценарий или заполни диагностику."
    else:
        lines = ["✅ Что делать тебе сегодня:"]
        for t in tasks[:3]:
            if isinstance(t, dict):
                lines.append(f"- {t.get('title','')}: {t.get('details','')}")
        txt = "\n".join(lines)
    return pm(user_id=user_id, text=txt, reply_markup=kb_autopilot_menu(), callback_query_id=ctx.callback_query_id)
