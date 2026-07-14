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
    if not tenant_id:
        raise ValueError("TENANT_ID_REQUIRED")
    product_id = required_str(payload, "product_id")
    order_id = required_str(payload, "order_id")

    # Business identity comes from the signed action payload. Arbitrary provider
    # metadata may add fields but can never replace tenant/product/order scope.
    metadata["tenant_id"] = tenant_id
    metadata["product_id"] = product_id
    metadata["order_id"] = order_id
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
    body = require_mapping(payload)
    return effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(body, "user_id"),
        amount=required_int(body, "amount", min_value=1),
        currency=required_str(body, "currency"),
        provider=str(body.get("provider", "yookassa") or "yookassa"),
        metadata=_payment_metadata(body, env),
    )


def handle_create_payment_and_send_link(payload, effects, env):
    body = require_mapping(payload)
    user_id = required_str(body, "user_id")
    tenant_id = _tenant_id(body, env)
    if not tenant_id:
        raise ValueError("TENANT_ID_REQUIRED")
    payment_result = effects.capture_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        amount=required_int(body, "amount", min_value=1),
        currency=required_str(body, "currency"),
        provider=str(body.get("provider", "yookassa") or "yookassa"),
        metadata=_payment_metadata(body, env),
    )
    confirmation_url = None
    if isinstance(payment_result, dict):
        meta = payment_result.get("meta")
        provider_payload = (meta or {}).get("yookassa") if isinstance(meta, dict) else None
        if isinstance(provider_payload, dict):
            confirmation = (
                provider_payload.get("confirmation")
                if isinstance(provider_payload.get("confirmation"), dict)
                else {}
            )
            raw_url = confirmation.get("confirmation_url") or confirmation.get("url")
            confirmation_url = str(raw_url).strip() if raw_url else None
    message = (
        "Ссылка на оплату: " + confirmation_url
        if confirmation_url
        else "Платёж не подтверждён провайдером. Новая ссылка не создана."
    )
    delivery_result = effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=message,
        priority="high",
        critical=True,
    )
    payment_ok = bool(payment_result.get("ok")) if isinstance(payment_result, dict) else bool(payment_result)
    delivery_ok = bool(delivery_result.get("ok")) if isinstance(delivery_result, dict) else bool(delivery_result)
    payment_evidence = _trusted_effect_proof(payment_result)
    delivery_evidence = _trusted_effect_proof(delivery_result)
    composite_ok = bool(
        payment_ok
        and confirmation_url
        and delivery_ok
        and _proof_is_positive(payment_evidence)
        and _proof_is_positive(delivery_evidence)
    )
    return {
        "ok": composite_ok,
        "status": "verified" if composite_ok else "failed",
        "payment": payment_result,
        "delivery": delivery_result,
        "payment_evidence": payment_evidence,
        "delivery_evidence": delivery_evidence,
        "router_evidence": delivery_evidence if composite_ok else None,
        "feedback": {
            "connector_snapshots": [payment_evidence, delivery_evidence]
            if composite_ok
            else []
        },
    }


def handle_reconcile_payments(payload, effects, env):
    body = require_mapping(payload or {})
    window_min = int(body.get("window_min", 30))
    if window_min <= 0:
        raise ValueError("INVALID_WINDOW_MIN")
    return effects.reconcile_payments(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        window_min=window_min,
    )


def handle_reconcile_payment(payload, effects, env):
    body = require_mapping(payload)
    return effects.reconcile_payment(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        external_payment_id=required_str(body, "external_id"),
        notification_id=optional_str(body, "notification_id"),
        event=body.get("event"),
        user_id_hint=optional_str(body, "user_id"),
    )


def handle_grant_access(payload, effects, env):
    body = require_mapping(payload)
    track_payload = optional_dict(body, "track_payload")
    return effects.grant_access(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(body, "user_id"),
        tenant_id=required_str(body, "tenant_id"),
        product_id=required_str(body, "product_id"),
        grant_key=optional_str(body, "grant_key"),
        full_access=bool(body.get("full_access", True)),
        notify_text=optional_str(body, "notify_text"),
        notify_reply_markup=optional_dict(body, "notify_reply_markup"),
        track_event_type=optional_str(body, "track_event_type"),
        track_payload=track_payload,
    )


def handle_deploy_policy(payload, effects, env):
    body = require_mapping(payload)
    rollout_pct = required_int(body, "rollout_pct", min_value=0)
    if rollout_pct > 100:
        raise ValueError("INVALID_ROLLOUT_PCT")
    return effects.deploy_policy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(body, "tenant_id"),
        candidate_policy_id=required_str(body, "candidate_policy_id"),
        rollout_pct=rollout_pct,
    )


def handle_rollback_policy(payload, effects, env):
    body = require_mapping(payload)
    return effects.rollback_policy(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(body, "tenant_id"),
        reason=required_str(body, "reason"),
    )
