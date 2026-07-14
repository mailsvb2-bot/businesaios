from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from core.events.event_types import REWARD_OBSERVE
from core.events.log import EventLog
from execution.verification.evidence_types import evidence_status_is_positive
from runtime.actions import ACTION_REWARD_OBSERVE_V1
from runtime.ads import RewardComputer, RewardWindow
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.governance import ProfitMetricsService
from runtime.handlers.route_failure_support import (
    best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_REWARD_OBSERVE_V1
_OBSERVATION_NAMESPACE = uuid.UUID("ff81e66e-0d46-4e7a-8637-cf0f38de747d")


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = delivery.get(key)
        if isinstance(candidate, Mapping) and str(candidate.get("source") or "").strip():
            return dict(candidate)
    return None


def _proof_is_positive(proof: Mapping[str, Any] | None) -> bool:
    if not isinstance(proof, Mapping) or proof.get("verified") is False:
        return False
    return evidence_status_is_positive(proof.get("status")) or proof.get("verified") is True


def _blocked(
    *,
    payload: dict[str, Any],
    effects: EffectsPort,
    decision_id: str,
    correlation_id: str,
    reason: str,
    exc: Exception,
) -> dict[str, Any]:
    delivery = effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=str(payload.get("tenant_id") or "").strip(),
        user_id=str(payload.get("user_id") or ""),
        text=safe_route_blocked_text("Reward observe"),
        track_event_type="reward_observe_blocked@v1",
        track_payload=blocked_error_payload(reason=reason, exc=exc),
        channel=str(payload.get("channel") or "telegram"),
        channel_policy=(
            dict(payload.get("channel_policy") or {})
            if isinstance(payload.get("channel_policy"), Mapping)
            else None
        ),
    )
    return {
        "ok": False,
        "status": "blocked",
        "reason": reason,
        "delivery": delivery,
        "router_evidence": None,
    }


def _observation_event_id(*, tenant_id: str, decision_id: str) -> str:
    return str(
        uuid.uuid5(
            _OBSERVATION_NAMESPACE,
            f"businesaios:reward-observe:{tenant_id}:{decision_id}",
        )
    )


def _load_observation(
    *,
    event_store: Any,
    tenant_id: str,
    decision_id: str,
) -> tuple[dict[str, Any], str] | None:
    events = EventLog(event_store, tenant=str(tenant_id)).get_events(
        str(decision_id),
        REWARD_OBSERVE,
    )
    for event in reversed(events):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if int(payload.get("schema_version") or 0) != 1:
            continue
        if "reward_minor" not in payload:
            continue
        event_id = str(event.get("event_id") or "").strip()
        if event_id:
            return dict(payload), event_id
    return None


def _persist_observation(
    *,
    event_store: Any,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    observation: dict[str, Any],
) -> str:
    event_id = _observation_event_id(
        tenant_id=tenant_id,
        decision_id=decision_id,
    )
    log = EventLog(event_store, tenant=str(tenant_id))
    try:
        log.emit(
            event_id=event_id,
            event_type=REWARD_OBSERVE,
            source="ads_rl",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=dict(observation),
        )
    except Exception:
        raced = _load_observation(
            event_store=event_store,
            tenant_id=tenant_id,
            decision_id=decision_id,
        )
        if raced is None or raced[0] != observation:
            raise
        return raced[1]
    return event_id


def _ledger_evidence(
    *,
    event_id: str,
    tenant_id: str,
    reward_minor: int,
) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "reward_observation_recorded",
        "external_refs": [str(event_id)],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "reward_minor": int(reward_minor),
        },
    }


def _bounded_days(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(1, min(365, parsed))


def handle_reward_observe(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    body = dict(payload or {})
    try:
        route = extract_strict_route_from_envelope(payload=body, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        decision_id, correlation_id = best_effort_route_ids(payload=body, env=env)
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            reason="route_violation",
            exc=exc,
        )

    try:
        tenant_id = str(body.get("tenant_id") or "").strip()
        user_id = str(body.get("user_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        if not user_id:
            raise DecisionRouteViolation("user_id is required")
        if event_store is None:
            raise RuntimeError("canonical event store is unavailable")

        existing = _load_observation(
            event_store=event_store,
            tenant_id=tenant_id,
            decision_id=route.decision_id,
        )
        if existing is None:
            metrics = (
                dict(body.get("metrics") or {})
                if isinstance(body.get("metrics"), Mapping)
                else {}
            )
            source_decision_id = str(
                metrics.get("source_decision_id")
                or metrics.get("decision_id")
                or route.decision_id
            ).strip()
            lookback_days = _bounded_days(
                body.get("lookback_days") or metrics.get("lookback_days"),
                default=14,
            )
            reward = RewardComputer(
                profit_metrics=ProfitMetricsService(event_store=event_store),
                window=RewardWindow(
                    pre_days=_bounded_days(metrics.get("pre_days"), default=3),
                    post_days=_bounded_days(metrics.get("post_days"), default=3),
                ),
            )
            transition = reward.transition_for_decision(
                tenant_id=tenant_id,
                decision_id=source_decision_id,
                lookback_days=lookback_days,
            )
            if transition is None:
                raise RuntimeError("canonical reward transition is unavailable")
            observation = {
                "schema_version": 1,
                "tenant_id": tenant_id,
                "source_decision_id": source_decision_id,
                "reward_minor": int(transition.reward_minor),
                "state": dict(transition.state or {}),
                "action": dict(transition.action or {}),
                "meta": dict(transition.meta or {}),
            }
            completion_event_id = _persist_observation(
                event_store=event_store,
                tenant_id=tenant_id,
                user_id=user_id,
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                observation=observation,
            )
        else:
            observation, completion_event_id = existing
    except DecisionRouteViolation as exc:
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            reason="route_violation",
            exc=exc,
        )
    except Exception as exc:
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            reason="reward_observe_failed",
            exc=exc,
        )

    reward_minor = int(observation.get("reward_minor") or 0)
    generation_evidence = _ledger_evidence(
        event_id=completion_event_id,
        tenant_id=tenant_id,
        reward_minor=reward_minor,
    )
    delivery = effects.send_message(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=f"📈 Reward observed: {reward_minor} minor units",
        channel=str(body.get("channel") or "telegram"),
        channel_policy=(
            dict(body.get("channel_policy") or {})
            if isinstance(body.get("channel_policy"), Mapping)
            else None
        ),
        critical=False,
    )
    delivery_evidence = _delivery_evidence(delivery)
    delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
    verified = bool(
        completion_event_id
        and delivery_ok
        and _proof_is_positive(delivery_evidence)
    )
    return {
        "ok": verified,
        "status": "verified" if verified else "failed",
        "observation": observation,
        "completion_event_id": completion_event_id,
        "delivery": delivery,
        "router_evidence": generation_evidence if verified else None,
        "feedback": {
            "connector_snapshots": [generation_evidence, delivery_evidence]
            if verified and delivery_evidence is not None
            else []
        },
    }
