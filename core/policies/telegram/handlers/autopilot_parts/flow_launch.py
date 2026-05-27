from __future__ import annotations

from core.autopilot.pricing import recommend_price_minor
from core.autopilot.resolver import resolve_autopilot_contract
from core.autopilot.stop_loss import build_stop_loss_plan
from core.autopilot.tasks import build_tasks_from_diagnostics, serialize_tasks
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.policies.telegram.handlers.autopilot_parts.menu_and_dashboards import stop_loss_verdict
from core.policies.telegram.helpers import propose
from core.ux.telegram_keyboards import kb_autopilot_menu

AUTOPILOT_RUN_STARTED_V1 = "autopilot_run_started@v1"
AUTOPILOT_DECISION_V1 = "autopilot_decision@v1"
AUTOPILOT_STARTED_V1 = "autopilot_started@v1"


def build_launch_action(ctx, *, user_id: str, default_price_rub: int, sess: dict, sl, logger):
    tenant_id = normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None))
    contract = resolve_autopilot_contract(product=getattr(ctx.state, "product", {}) or {}, tenant_id=tenant_id)

    diag = dict(sess.get("diag") or {}) if isinstance(sess.get("diag"), dict) else {}
    tasks = serialize_tasks(build_tasks_from_diagnostics(diag))
    sess["tasks"] = tasks
    sess["stage"] = "running"

    verdict = stop_loss_verdict(ctx, contract=contract, logger=logger)
    if (not verdict.allow) and (not sl.active):
        sess_a = dict(sess)
        sess_a["stage"] = "audit:stop_loss"
        return propose(
            "execute_plan@v1",
            build_stop_loss_plan(
                user_id=str(user_id),
                verdict=verdict,
                existing=sl,
                session_patch=sess_a,
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
    changes = {"suggested_price_minor": int(rec.price_minor), "currency": rec.currency}
    tasks_text = "\n".join([f"- {t.get('title', '')}: {t.get('details', '')}" for t in tasks])

    return propose(
        "execute_plan@v1",
        {
            "user_id": str(user_id),
            "steps": [
                {
                    "action": "emit_event@v1",
                    "payload": {
                        "user_id": str(user_id),
                        "event_type": AUTOPILOT_RUN_STARTED_V1,
                        "payload": {"goal": "profit_7d", "diagnostic": diag},
                        "source": "autopilot",
                    },
                },
                {
                    "action": "emit_event@v1",
                    "payload": {
                        "user_id": str(user_id),
                        "event_type": AUTOPILOT_DECISION_V1,
                        "payload": {
                            "kind": "price_reco",
                            "reason": rec.reason,
                            "changes": changes,
                            "guardrails": {"allow": bool(verdict.allow), "reason": verdict.reason},
                        },
                        "source": "autopilot",
                    },
                },
                {
                    "action": "set_user_setting@v1",
                    "payload": {"user_id": str(user_id), "key": "autopilot:session", "value": dict(sess)},
                },
                {
                    "action": "send_message@v1",
                    "payload": {
                        "user_id": str(user_id),
                        "text": (
                            "✅ Запустил автопилот на 7 дней.\n\n"
                            "Вот что делать сегодня (1–3 задачи):\n"
                            f"{tasks_text}\n\n"
                            "Открой дашборд: ‘Сегодня’ → ‘Что сделал автопилот’."
                        ),
                        "reply_markup": kb_autopilot_menu(),
                        "callback_query_id": ctx.callback_query_id,
                        "track_event_type": AUTOPILOT_STARTED_V1,
                        "track_payload": {"goal": "profit_7d"},
                    },
                },
            ],
        },
    )
