from __future__ import annotations

from runtime.handler_impl.core.payloads import optional_dict, optional_str, require_mapping, required_str
from runtime.tenancy import normalize_tenant_id


def handle_admin_set_role(payload, effects, env):
    payload = require_mapping(payload)
    return effects.admin_set_role(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
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
        tenant_id=required_str(payload, "tenant_id"),
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
        tenant_id=required_str(payload, "tenant_id"),
        admin_id=required_str(payload, "admin_id"),
        step_key=required_str(payload, "step_key"),
        variant_a=required_str(payload, "variant_a"),
        variant_b=required_str(payload, "variant_b"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )


def _tenant_id(payload: dict, env) -> str:
    decision = getattr(env, "decision", None)
    candidates = (
        payload.get("tenant_id"),
        getattr(decision, "tenant_id", None) if decision is not None else None,
        getattr(env, "tenant_id", None),
    )
    for candidate in candidates:
        tenant_id = normalize_tenant_id(candidate)
        if tenant_id:
            return tenant_id
    return ""


def handle_admin_user_card(payload, effects, env, *, event_store):
    payload = require_mapping(payload or {})
    tenant_id = _tenant_id(payload, env)
    product_id = optional_str(payload, "product_id")
    admin_id = optional_str(payload, "admin_id") or ""
    target = optional_str(payload, "target_user_id") or ""
    if not tenant_id or not admin_id or not target:
        return effects.send_message(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            tenant_id=tenant_id,
            user_id=admin_id or "system",
            text="Некорректный запрос: не указан бизнес, администратор или пользователь.",
            reply_markup=None,
        )

    try:
        from core.entitlements.read_model import compute_entitlements
        from core.payments.read_model import latest_payment_status
        from core.users.read_model import selected_tariff, user_settings

        payment = latest_payment_status(
            event_store=event_store,
            tenant_id=tenant_id,
            product_id=product_id,
            user_id=target,
        )
        entitlements = compute_entitlements(
            event_store=event_store,
            tenant_id=tenant_id,
            product_id=product_id,
            user_id=target,
        )
        settings = user_settings(
            event_store,
            tenant_id=tenant_id,
            user_id=target,
        )
        tariff = selected_tariff(
            event_store,
            tenant_id=tenant_id,
            product_id=product_id,
            user_id=target,
        )
        access = "полный" if bool(entitlements.get("full_access")) else "базовый"
        payment_status = str(payment.get("status") or "none")
        city = str(settings.get("city") or "-")
        tariff_title = str((tariff or {}).get("title") or (tariff or {}).get("tariff") or "-")
        scope_line = (
            f"Продукт: {product_id}\n"
            if product_id
            else "Продукты с доступом: " + ", ".join(entitlements.get("product_ids") or []) + "\n"
        )
        text = (
            "🔎 Карточка пользователя\n\n"
            f"Бизнес: {tenant_id}\n"
            f"{scope_line}"
            f"ID: {target}\n"
            f"Доступ: {access}\n"
            f"Оплата: {payment_status}\n"
            f"Город: {city}\n"
            f"Тариф (выбор): {tariff_title}\n"
        )
    except Exception:
        product_line = f"\nПродукт: {product_id}" if product_id else ""
        text = f"🔎 Карточка пользователя\n\nБизнес: {tenant_id}{product_line}\nID: {target}\n(не удалось собрать данные)"

    return effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id,
        user_id=admin_id,
        text=text,
        reply_markup=None,
    )
