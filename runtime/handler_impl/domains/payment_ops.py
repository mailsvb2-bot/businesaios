from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.verification.evidence_types import evidence_status_is_positive
from runtime.handler_impl.core.payloads import optional_dict, optional_str, require_mapping, required_int, required_str
from runtime.tenancy import normalize_tenant_id


def _tenant_id(payload: Mapping[str, Any], env) -> str:
    decision = getattr(env, "decision", None)
    for candidate in (
        payload.get("tenant_id"),
        getattr(decision, "tenant_id", None) if decision is not None else None,
        getattr(env, "tenant_id", None),
    ):
        tenant_id = normalize_tenant_id(candidate)
        if tenant_id:
            return tenant_id
    return ""


def _payment_metadata(payload: Mapping[str, Any], env) -> dict[str, Any]:
    metadata = optional_dict(payload, "metadata") or {}
    tenant_id = _tenant_id(payload, env)
    if tenant_id:
        metadata.setdefault("tenant_id", tenant_id)
    product_id = optional_str(payload, "product_id")
    if product_id:
        metadata.setdefault("product_id", product_id)
    order_id = optional_str(payload, "order_id") or str(env.decision.decision_id)
    metadata.setdefault("order_id", order_id)
    return metadata


def _trusted_effect_proof(result: object) -> dict[str, Any] | None:
    if not isinstance(result, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = result.get(key)
        if isinstance(candidate, Mapping) and str(candidate.get("source") or "").strip():
            return dict(candidate)
    return None


def _proof_is_positive(proof: Mapping[str, Any] | None) -> bool:
    if not isinstance(proof, Mapping):
        return False
    if proof.get("verified") is False:
        return False
    return evidence_status_is_positive(proof.get("status")) or proof.get("verified") is True


def handle_capture_payment(payload, effects, env):
    payload = require_mapping(payload)
    return effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        amount=required_int(payload, "amount", min_value=1),
        currency=required_str(payload, "currency"),
        provider=str(payload.get("provider", "yookassa") or "yookassa"),
        metadata=_payment_metadata(payload, env),
    )


def handle_create_payment_and_send_link(payload, effects, env):
    payload = require_mapping(payload)
    user_id = required_str(payload, "user_id")
    tenant_id = _tenant_id(payload, env)
    pay_res = effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        amount=required_int(payload, "amount", min_value=1),
        currency=required_str(payload, "currency"),
        provider=str(payload.get("provider", "yookassa") or "yookassa"),
        metadata=_payment_metadata(payload, env),
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
    delivery_res = effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=msg,
        priority="high",
        critical=True,
    )
    payment_ok = bool(pay_res.get("ok")) if isinstance(pay_res, dict) else bool(pay_res)
    delivery_ok = bool(delivery_res.get("ok")) if isinstance(delivery_res, dict) else bool(delivery_res)
    payment_evidence = _trusted_effect_proof(pay_res)
    delivery_evidence = _trusted_effect_proof(delivery_res)
    composite_ok = bool(
        payment_ok
        and delivery_ok
        and _proof_is_positive(payment_evidence)
        and _proof_is_positive(delivery_evidence)
    )
    feedback = {
        "connector_snapshots": [payment_evidence, delivery_evidence]
        if composite_ok
        else []
    }
    return {
        "ok": composite_ok,
        "status": "verified" if composite_ok else "failed",
        "payment": pay_res,
        "delivery": delivery_res,
        "payment_evidence": payment_evidence,
        "delivery_evidence": delivery_evidence,
        "router_evidence": delivery_evidence if composite_ok else None,
        "feedback": feedback,
    }


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
        tenant_id=required_str(payload, "tenant_id"),
        product_id=required_str(payload, "product_id"),
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
        tenant_id=required_str(payload, "tenant_id"),
        candidate_policy_id=required_str(payload, "candidate_policy_id"),
        rollout_pct=rollout_pct,
    )


def handle_rollback_policy(payload, effects, env):
    payload = require_mapping(payload)
    return effects.rollback_policy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        reason=required_str(payload, "reason"),
    )
