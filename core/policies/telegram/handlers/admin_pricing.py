"""Admin pricing session handler.

Extracted from telegram router to prevent router from becoming a god-module
and to make the pricing governance flow testable and auditable.
"""

from __future__ import annotations

from collections.abc import Callable

from core.policies.telegram.context import TelegramCtx, policy_scope, scoped_plan
from core.policies.telegram.handlers.admin.pricing_support import pricing_change_request_payload
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_staff_menu


def handle_admin_pricing_session(
    ctx: TelegramCtx,
    *,
    user_id: str,
    pm: Callable[[str, dict | None, str | None, dict | None], ProposedAction],
) -> ProposedAction | None:
    """Handle the admin free-text pricing governance session.

    Returns ProposedAction if handled, otherwise None.
    """

    if not (ctx.is_admin and isinstance(ctx.text, str) and ctx.text.strip()):
        return None

    sess: dict = {}
    try:
        if isinstance(ctx.settings, dict):
            sess = dict(ctx.settings.get("admin:pricing_session") or {})
    except Exception:
        sess = {}

    stage = str(sess.get("stage") or "").strip()
    if stage not in {"await_price", "await_approve_version"}:
        return None

    raw = ctx.text.strip()
    if raw.lower() in {"cancel", "отмена"}:
        return propose(
            "set_user_setting@v1",
            {
                "user_id": user_id,
                "key": "admin:pricing_session",
                "value": {},
                "notify_text": "✅ Ок, отменил pricing-сессию.",
                "notify_reply_markup": kb_staff_menu(),
            },
        )

    if stage == "await_price":
        parts = [p for p in raw.replace("\n", " ").split(" ") if p.strip()]
        if not parts:
            return pm("Введите цену числом (например: 2290 или 2290 v20.1).", kb_staff_menu(), None, None)
        try:
            price = int(parts[0])
        except Exception:
            return pm("Не понял цену. Формат: 2290 или 2290 v20.1", kb_staff_menu(), None, None)

        suggested_v = str(parts[1]).strip() if len(parts) >= 2 else ""
        try:
            plan_id = int(sess.get("plan_id") or 0)
        except Exception:
            plan_id = 0
        if plan_id <= 0:
            return pm("Сессия сломалась (plan_id). Открой pricing menu заново.", kb_staff_menu(), None, None)

        if price <= 0:
            return pm("Цена должна быть больше нуля.", kb_staff_menu(), None, None)
        if scoped_plan(ctx, plan_id) is None or not policy_scope(ctx).has_business:
            return pm("Бизнес или тариф не выбран. Открой pricing menu заново.", kb_staff_menu(), None, None)
        return propose("request_pricing_change@v1", pricing_change_request_payload(
            admin_id=str(user_id), plan_id=plan_id, new_price=price,
            nonce=str(sess.get("nonce") or ""),
            suggested_pricing_version=suggested_v, callback_query_id=ctx.callback_query_id,
        ))

    # stage == await_approve_version
    version = raw.strip()
    if not version:
        return pm("Введите PRICING_VERSION (например v20.1) или cancel.", kb_staff_menu(), None, None)
    rid = str(sess.get("request_id") or "").strip()
    if not rid:
        return pm("Сессия сломалась (request_id). Открой pending заново.", kb_staff_menu(), None, None)

    reqs = []
    if isinstance(ctx.admin_metrics, dict):
        reqs = list(ctx.admin_metrics.get("pricing_requests") or [])
    match = None
    for r in reqs:
        if str(r.get("request_id") or "") == rid:
            match = r
            break
    scope = policy_scope(ctx)
    if (not match or not scope.has_business
            or str(match.get("product_id") or "") != scope.product_id
            or str(match.get("business_id") or "") != scope.business_id):
        return pm("Не нашёл этот request в текущем бизнесе. Обнови pending.", kb_staff_menu(), None, None)
    if str(match.get("status")) != "pending":
        return pm("Этот request уже не pending.", kb_staff_menu(), None, None)

    plan_id = int(match.get("plan_id") or 0)
    price = int(match.get("new_price") or 0)
    requested_by = str(match.get("requested_by") or "")

    if plan_id <= 0 or price <= 0 or scoped_plan(ctx, plan_id) is None:
        return pm("Request содержит неверный тариф или цену.", kb_staff_menu(), None, None)

    # Governance: separation of duties (initiator != approver)
    if requested_by and str(requested_by) == str(user_id):
        return pm(
            "⛔ Нельзя самому подтверждать свой change-request.\n\n"
            "Попроси другого администратора из ADMIN_USER_IDS открыть ‘Pending requests’ и нажать Approve.",
            kb_staff_menu(),
            None,
            None,
        )

    return propose(
        "apply_pricing_change@v1",
        {
            "admin_id": str(user_id),
            "plan_id": plan_id,
            "new_price": price,
            "pricing_version": version[:64],
            "request_id": rid,
            "notify_text": f"✅ Применил: plan #{plan_id} → {price}₽ (PRICING_VERSION={version}).",
            "notify_reply_markup": kb_staff_menu(),
        },
    )
