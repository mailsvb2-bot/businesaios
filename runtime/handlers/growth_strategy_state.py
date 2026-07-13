from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.verification.evidence_types import evidence_status_is_positive
from runtime.growth import GrowthStrategyService
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME_ACCEPT = "growth_strategy_accept@v1"
ACTION_NAME_REJECT = "growth_strategy_reject@v1"


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key.upper()}_REQUIRED")
    return value


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        value = delivery.get(key)
        if isinstance(value, Mapping) and str(value.get("source") or "").strip():
            return dict(value)
    return None


def _proof_is_positive(proof: Mapping[str, Any] | None) -> bool:
    if not isinstance(proof, Mapping) or proof.get("verified") is False:
        return False
    return evidence_status_is_positive(proof.get("status")) or proof.get("verified") is True


def _ledger_evidence(*, event_id: str, tenant_id: str, hypothesis_id: str, state: str) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "growth_hypothesis_state_recorded",
        "external_refs": [str(event_id)],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "hypothesis_id": str(hypothesis_id),
            "state": str(state),
        },
    }


def handle_growth_strategy_accept(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    return _handle(payload, effects, env, event_store=event_store, state="accepted")


def handle_growth_strategy_reject(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    return _handle(payload, effects, env, event_store=event_store, state="rejected")


def _handle(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any, state: str) -> Any:
    body = dict(payload or {})
    tenant_id = _required_text(body, "tenant_id")
    user_id = _required_text(body, "user_id")
    hypothesis_id = _required_text(body, "hypothesis_id")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)

    service = GrowthStrategyService(event_store=event_store, llm=None)
    if state == "accepted":
        event_id = service.accept_hypothesis(
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            hypothesis_id=hypothesis_id,
        )
        text = f"✅ Принято: {hypothesis_id}"
        action = ACTION_NAME_ACCEPT
    else:
        event_id = service.reject_hypothesis(
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            hypothesis_id=hypothesis_id,
        )
        text = f"❌ Отклонено: {hypothesis_id}"
        action = ACTION_NAME_REJECT

    state_evidence = _ledger_evidence(
        event_id=event_id,
        tenant_id=tenant_id,
        hypothesis_id=hypothesis_id,
        state=state,
    )
    notification = effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reply_markup={"inline_keyboard": [[{"text": "📋 Backlog", "callback_data": "growth:backlog"}]]},
        callback_query_id=body.get("callback_query_id"),
        critical=False,
        track_event_type=action,
        track_payload={
            "tenant_id": tenant_id,
            "hypothesis_id": hypothesis_id,
            "state_event_id": event_id,
        },
    )
    notification_evidence = _delivery_evidence(notification)
    notification_ok = bool(notification.get("ok")) if isinstance(notification, Mapping) else bool(notification)
    composite_ok = bool(event_id and notification_ok and _proof_is_positive(notification_evidence))

    return {
        "ok": composite_ok,
        "status": "verified" if composite_ok else "failed",
        "state_change": {
            "tenant_id": tenant_id,
            "hypothesis_id": hypothesis_id,
            "state": state,
            "event_id": event_id,
        },
        "notification": notification,
        "router_evidence": state_evidence if composite_ok else None,
        "feedback": {
            "connector_snapshots": [state_evidence, notification_evidence]
            if composite_ok and notification_evidence is not None
            else []
        },
    }
