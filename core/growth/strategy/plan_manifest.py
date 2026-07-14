from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from core.events.log import EventLog
from core.tenancy.scope import TenantScope

from .contracts import GrowthGoalV1, GrowthHypothesisV1, GrowthSignalV1, StrategyPlanV1
from .event_types import GROWTH_STRATEGY_PLAN_MANIFEST

_MANIFEST_NAMESPACE = uuid.UUID("8095423c-7bcf-4a5c-987d-8cc27a721137")


def _manifest_event_id(*, tenant_id: str, decision_id: str) -> str:
    return str(
        uuid.uuid5(
            _MANIFEST_NAMESPACE,
            f"businesaios:growth-plan:{tenant_id}:{decision_id}",
        )
    )


def _decode_goal(raw: object) -> GrowthGoalV1:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    data["constraints"] = tuple(str(item) for item in data.get("constraints") or ())
    return GrowthGoalV1(**data)


def _decode_signals(raw: object) -> GrowthSignalV1:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    data["top_channels"] = tuple(str(item) for item in data.get("top_channels") or ())
    data["notes"] = tuple(str(item) for item in data.get("notes") or ())
    return GrowthSignalV1(**data)


def _decode_hypothesis(raw: object) -> GrowthHypothesisV1:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    data["action_hints"] = dict(data.get("action_hints") or {})
    return GrowthHypothesisV1(**data)


def _decode_plan(payload: dict[str, Any]) -> StrategyPlanV1 | None:
    raw = payload.get("plan")
    if not isinstance(raw, dict):
        return None
    try:
        return StrategyPlanV1(
            schema_version=int(raw.get("schema_version") or 1),
            tenant_id=str(raw.get("tenant_id") or ""),
            created_ms=int(raw.get("created_ms") or 0),
            goal=_decode_goal(raw.get("goal")),
            signals=_decode_signals(raw.get("signals")),
            top_hypotheses=tuple(
                _decode_hypothesis(item)
                for item in list(raw.get("top_hypotheses") or ())
                if isinstance(item, dict)
            ),
            notes=tuple(str(item) for item in raw.get("notes") or ()),
        )
    except (TypeError, ValueError):
        return None


def load_plan_manifest(
    event_store: Any,
    *,
    tenant_id: str,
    decision_id: str,
) -> tuple[StrategyPlanV1, str] | None:
    log = EventLog(event_store, tenant=TenantScope(str(tenant_id)))
    events = log.get_events(str(decision_id), GROWTH_STRATEGY_PLAN_MANIFEST)
    for event in reversed(events):
        plan = _decode_plan(dict(event.get("payload") or {}))
        if plan is not None:
            return plan, str(event.get("event_id") or "")
    return None


def persist_plan_manifest(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    plan: StrategyPlanV1,
) -> str:
    existing = load_plan_manifest(
        event_store,
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
    )
    if existing is not None:
        existing_plan, event_id = existing
        if existing_plan != plan:
            raise RuntimeError("GROWTH_PLAN_MANIFEST_CONFLICT")
        return event_id

    event_id = _manifest_event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
    )
    log = EventLog(event_store, tenant=TenantScope(str(tenant_id)))
    try:
        log.emit(
            event_id=event_id,
            event_type=GROWTH_STRATEGY_PLAN_MANIFEST,
            source="growth_strategy",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            timestamp_ms=int(plan.created_ms),
            payload={
                "schema_version": 1,
                "plan": asdict(plan),
            },
        )
    except Exception:
        raced = load_plan_manifest(
            event_store,
            tenant_id=str(tenant_id),
            decision_id=str(decision_id),
        )
        if raced is None or raced[0] != plan:
            raise
        return raced[1]
    return event_id


__all__ = ["load_plan_manifest", "persist_plan_manifest"]
