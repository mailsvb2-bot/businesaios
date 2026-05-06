from __future__ import annotations

from runtime.handler_impl.core.payloads import optional_dict, optional_str, require_mapping, required_str


def handle_admin_set_role(payload, effects, env):
    payload = require_mapping(payload)
    return effects.admin_set_role(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        target_user_id=required_str(payload, "target_user_id"),
        role=required_str(payload, "role"),
        enabled=bool(payload.get("enabled", True)),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )


def handle_admin_set_perm(payload, effects, env):
    payload = require_mapping(payload)
    return effects.admin_set_perm(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        target_user_id=required_str(payload, "target_user_id"),
        perm=required_str(payload, "perm"),
        enabled=bool(payload.get("enabled", True)),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )


def handle_set_marketing_copy(payload, effects, env):
    payload = require_mapping(payload)
    return effects.set_marketing_copy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        admin_id=required_str(payload, "admin_id"),
        step_key=required_str(payload, "step_key"),
        variant_a=required_str(payload, "variant_a"),
        variant_b=required_str(payload, "variant_b"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )


def handle_admin_user_card(payload, effects, env, *, event_store):
    payload = require_mapping(payload or {})
    admin_id = optional_str(payload, "admin_id") or ""
    target = optional_str(payload, "target_user_id") or ""
    if not admin_id or not target:
        return effects.send_message(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            user_id=admin_id or "system",
            text="Некорректный запрос.",
            reply_markup=None,
        )
    try:
        from core.payments.read_model import latest_payment_status
        from core.entitlements.read_model import compute_entitlements
        from core.users.read_model import user_settings, selected_tariff, mood_last

        pay = latest_payment_status(event_store=event_store, user_id=target)
        ent = compute_entitlements(event_store, user_id=target)
        s = user_settings(event_store, user_id=target)
        tariff = selected_tariff(event_store, user_id=target)
        moods = mood_last(event_store, user_id=target, limit=5)
        access = "полный" if bool(ent.get("full_access")) else "базовый"
        pay_status = str(pay.get("status") or "none")
        city = str(s.get("city") or "-")
        tariff_title = str((tariff or {}).get("title") or (tariff or {}).get("tariff") or "-")
        mood_line = "-"
        if moods:
            last = moods[-1]
            sc = last.get("score")
            note = (last.get("note") or "").strip().replace("\n", " ")[:80]
            mood_line = f"{sc}/10" + (f" — {note}" if note else "")
        txt = (
            "🔎 Карточка пользователя\n\n"
            f"ID: {target}\nДоступ: {access}\nОплата: {pay_status}\n"
            f"Город: {city}\nТариф (выбор): {tariff_title}\nПоследнее состояние: {mood_line}\n"
        )
    except Exception:
        txt = f"🔎 Карточка пользователя\n\nID: {target}\n(не удалось собрать данные)"
    return effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=admin_id,
        text=txt,
        reply_markup=None,
    )
