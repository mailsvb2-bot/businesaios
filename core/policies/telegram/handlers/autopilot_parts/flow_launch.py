from __future__ import annotations

from core.autopilot.pricing import recommend_price_minor
from core.autopilot.resolver import resolve_autopilot_contract
from core.autopilot.stop_loss import build_stop_loss_plan
from core.autopilot.tasks import build_tasks_from_diagnostics, serialize_tasks
from core.policies.telegram.context import operator_flag
from core.policies.telegram.handlers.autopilot_parts.menu_and_dashboards import stop_loss_verdict
from core.policies.telegram.helpers import propose
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.ux.telegram_keyboards import kb_autopilot_menu

AUTOPILOT_RUN_STARTED_V1 = "autopilot_run_started@v1"
AUTOPILOT_DECISION_V1 = "autopilot_decision@v1"
AUTOPILOT_STARTED_V1 = "autopilot_started@v1"


def build_launch_action(
    ctx,
    *,
    user_id: str,
    default_price_rub: int,
    sess: dict,
    sl,
    logger,
):
    tenant_id = normalize_tenant_id_or_unknown(
        getattr(ctx.state, "tenant_id", None)
    )
    contract = resolve_autopilot_contract(
        product=getattr(ctx.state, "product", {}) or {},
        tenant_id=tenant_id,
    )

    diag = dict(sess.get("diag") or {}) if isinstance(sess.get("diag"), dict) else {}
    tasks = serialize_tasks(build_tasks_from_diagnostics(diag))
    sess["tasks"] = tasks

    verdict = stop_loss_verdict(ctx, contract=contract, logger=logger)
    if not verdict.allow:
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

    try:
        base_price_minor = int(diag.get("avg_check_rub") or default_price_rub) * 100
    except Exception:
        base_price_minor = int(default_price_rub) * 100
    rec = recommend_price_minor(
        base_price_minor=base_price_minor,
        currency="RUB",
        stats={},
        seed=str(ctx.marketing_seed or "1"),
        user_id=str(user_id),
    )
    tasks_text = "\n".join(
        [f"- {task.get('title', '')}: {task.get('details', '')}" for task in tasks]
    )

    if operator_flag(ctx, "autopilot_execute"):
        return propose("ads_autopilot_tick@v1", {
            "user_id": str(user_id),
            "objective": str(contract.north_star_metric or "profit"),
            "max_daily_budget_minor": int(contract.constraints.daily_budget_minor),
            "currency": str(contract.constraints.currency or "RUB"),
            "allowed_platforms": list(contract.safety_policy.allow_channels),
            **({"callback_query_id": ctx.callback_query_id} if ctx.callback_query_id else {}),
        })

    # No execution has occurred. Persist diagnostics and a human-readable plan.
    sess["stage"] = "planned"
    return propose(
        "set_user_setting@v1",
        {
            "user_id": str(user_id),
            "key": "autopilot:session",
            "value": dict(sess),
            "notify_text": (
                "🧭 Автопилот: режим «диагностика и план».\n\n"
                "Реальные действия пока не выполняются. Используйте подтверждённый сценарий для запуска.\n\n"
                "План на сегодня (1–3 задачи):\n"
                f"{tasks_text}\n\n"
                f"Ориентир цены: {int(rec.price_minor) // 100} {rec.currency}."
            ),
            "notify_reply_markup": kb_autopilot_menu(),
            "callback_query_id": ctx.callback_query_id,
        },
    )
