from __future__ import annotations

from runtime.handler_impl.core.payloads import optional_dict, optional_str, require_mapping, required_int, required_str


def handle_capture_payment(payload, effects, env):
    payload = require_mapping(payload)
    return effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        amount=required_int(payload, "amount", min_value=1),
        currency=required_str(payload, "currency"),
        provider=str(payload.get("provider", "yookassa") or "yookassa"),
        metadata=optional_dict(payload, "metadata"),
    )


def handle_create_payment_and_send_link(payload, effects, env):
    payload = require_mapping(payload)
    user_id = required_str(payload, "user_id")
    pay_res = effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        amount=required_int(payload, "amount", min_value=1),
        currency=required_str(payload, "currency"),
        provider=str(payload.get("provider", "yookassa") or "yookassa"),
        metadata=optional_dict(payload, "metadata"),
    )
    url = None
    if isinstance(pay_res, dict):
        meta = pay_res.get("meta")
        yk = (meta or {}).get("yookassa") if isinstance(meta, dict) else None
        if isinstance(yk, dict):
            conf = yk.get("confirmation") if isinstance(yk.get("confirmation"), dict) else {}
            raw = conf.get("confirmation_url") or conf.get("url")
            url = str(raw).strip() if raw else None
    msg = "Ссылка на оплату: " + url if url else "Платёж создан. Если ссылка не пришла — напиши /status через минуту."
    effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        text=msg,
        priority="high",
        critical=True,
    )
    return pay_res


def handle_reconcile_payments(payload, effects, env):
    payload = require_mapping(payload or {})
    window_min = int(payload.get("window_min", 30))
    if window_min <= 0:
        raise ValueError("INVALID_WINDOW_MIN")
    return effects.reconcile_payments(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        window_min=window_min,
    )


def handle_reconcile_payment(payload, effects, env):
    payload = require_mapping(payload)
    return effects.reconcile_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        external_payment_id=required_str(payload, "external_id"),
        notification_id=optional_str(payload, "notification_id"),
        event=payload.get("event"),
        user_id_hint=optional_str(payload, "user_id"),
    )


def handle_grant_access(payload, effects, env):
    payload = require_mapping(payload)
    track_payload = optional_dict(payload, "track_payload")
    return effects.grant_access(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        tenant_id=optional_str(payload, "tenant_id"),
        product_id=optional_str(payload, "product_id"),
        grant_key=optional_str(payload, "grant_key"),
        full_access=bool(payload.get("full_access", True)),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        track_event_type=optional_str(payload, "track_event_type"),
        track_payload=track_payload,
    )


def handle_deploy_policy(payload, effects, env):
    payload = require_mapping(payload)
    rollout_pct = required_int(payload, "rollout_pct", min_value=0)
    if rollout_pct > 100:
        raise ValueError("INVALID_ROLLOUT_PCT")
    return effects.deploy_policy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        candidate_policy_id=required_str(payload, "candidate_policy_id"),
        rollout_pct=rollout_pct,
    )


def handle_rollback_policy(payload, effects, env):
    payload = require_mapping(payload)
    return effects.rollback_policy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        reason=required_str(payload, "reason"),
    )
