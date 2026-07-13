from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from typing import Any

from core.events.log import EventLog
from core.tenancy.scope import TenantScope

from .contracts import (
    ExperimentSpecV1,
    GrowthGoalV1,
    GrowthHypothesisV1,
    GrowthSignalV1,
    OpportunityScoreV1,
    StrategyPlanV1,
)
from .event_types import (
    GROWTH_EXPERIMENT_CREATED,
    GROWTH_HYPOTHESIS_CREATED,
    GROWTH_HYPOTHESIS_SCORED,
    GROWTH_HYPOTHESIS_STATE,
    GROWTH_STRATEGY_GENERATED,
    GROWTH_STRATEGY_SNAPSHOT,
)

_GROWTH_EVENT_NAMESPACE = uuid.UUID("fb3667f7-8dbc-43c8-9085-c7d008e66063")


def now_ms() -> int:
    return int(time.time() * 1000)


def _event_id(*, tenant_id: str, decision_id: str, event_type: str, subject: str) -> str:
    key = f"businesaios:growth:{tenant_id}:{decision_id}:{event_type}:{subject}"
    return str(uuid.uuid5(_GROWTH_EVENT_NAMESPACE, key))


def _event_id_exists(log: EventLog, event_id: str) -> bool:
    try:
        return any(str(event.get("event_id") or "") == str(event_id) for event in log.iter_events())
    except Exception:
        return False


def _emit_once(
    log: EventLog,
    *,
    event_id: str,
    event_type: str,
    source: str,
    user_id: str,
    payload: dict[str, Any],
    decision_id: str,
    correlation_id: str,
    timestamp_ms: int,
) -> str:
    if _event_id_exists(log, event_id):
        return str(event_id)
    try:
        log.emit(
            event_id=str(event_id),
            event_type=str(event_type),
            source=str(source),
            user_id=str(user_id),
            payload=dict(payload),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            timestamp_ms=int(timestamp_ms),
        )
    except Exception:
        # Postgres is ON CONFLICT-safe; SQLite raises on duplicate PK. Recheck
        # after a concurrent writer so both backends expose one emit-once result.
        if not _event_id_exists(log, event_id):
            raise
    return str(event_id)


def append_strategy_snapshot(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    signals: GrowthSignalV1,
    goal: GrowthGoalV1 | None = None,
) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_STRATEGY_SNAPSHOT,
        subject="snapshot",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_STRATEGY_SNAPSHOT,
        source="growth_strategy",
        user_id=str(user_id),
        payload={
            "signals": asdict(signals),
            "goal": asdict(goal or GrowthGoalV1()),
        },
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )


def append_hypothesis(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    h: GrowthHypothesisV1,
) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_HYPOTHESIS_CREATED,
        subject=f"hypothesis:{h.hypothesis_id}",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_HYPOTHESIS_CREATED,
        source="growth_strategy",
        user_id=str(user_id),
        payload={"hypothesis": asdict(h)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )


def append_score(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    score: OpportunityScoreV1,
) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_HYPOTHESIS_SCORED,
        subject=f"score:{score.hypothesis_id}",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_HYPOTHESIS_SCORED,
        source="growth_strategy",
        user_id=str(user_id),
        payload={"score": asdict(score)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )


def append_strategy_generated(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    goal: GrowthGoalV1,
    hypothesis_ids: tuple[str, ...],
    created_ms: int,
    notes: tuple[str, ...],
) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_STRATEGY_GENERATED,
        subject="complete",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_STRATEGY_GENERATED,
        source="growth_strategy",
        user_id=str(user_id),
        payload={
            "goal": asdict(goal),
            "hypothesis_ids": list(hypothesis_ids),
            "created_ms": int(created_ms),
            "notes": list(notes),
        },
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=int(created_ms),
    )


def load_generated_plan_for_decision(
    event_store: Any,
    *,
    tenant_id: str,
    decision_id: str,
) -> tuple[StrategyPlanV1, str] | None:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    completed = log.get_events(str(decision_id), GROWTH_STRATEGY_GENERATED)
    if not completed:
        return None
    completion = completed[-1]
    completion_payload = dict(completion.get("payload") or {})
    ordered_ids = tuple(str(item) for item in completion_payload.get("hypothesis_ids") or () if str(item))

    snapshot_events = log.get_events(str(decision_id), GROWTH_STRATEGY_SNAPSHOT)
    hypothesis_events = log.get_events(str(decision_id), GROWTH_HYPOTHESIS_CREATED)
    if not snapshot_events:
        return None

    snapshot_payload = dict(snapshot_events[-1].get("payload") or {})
    try:
        signals = GrowthSignalV1(**dict(snapshot_payload.get("signals") or {}))
    except Exception:
        return None
    try:
        goal = GrowthGoalV1(**dict(completion_payload.get("goal") or snapshot_payload.get("goal") or {}))
    except Exception:
        goal = GrowthGoalV1()

    by_id: dict[str, GrowthHypothesisV1] = {}
    for event in hypothesis_events:
        try:
            hypothesis = GrowthHypothesisV1(**dict((event.get("payload") or {}).get("hypothesis") or {}))
        except Exception:
            continue
        if hypothesis.hypothesis_id:
            by_id[hypothesis.hypothesis_id] = hypothesis
    hypotheses = tuple(by_id[item] for item in ordered_ids if item in by_id)
    if len(hypotheses) != len(ordered_ids):
        return None

    return (
        StrategyPlanV1(
            tenant_id=str(tenant_id),
            created_ms=int(completion_payload.get("created_ms") or completion.get("timestamp_ms") or 0),
            goal=goal,
            signals=signals,
            top_hypotheses=hypotheses,
            notes=tuple(str(item) for item in completion_payload.get("notes") or ("resumed",)),
        ),
        str(completion.get("event_id") or ""),
    )


def set_hypothesis_state(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    hypothesis_id: str,
    state: str,
    note: str = "",
) -> str:
    if state not in {"accepted", "rejected", "archived"}:
        raise ValueError("invalid_state")
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_HYPOTHESIS_STATE,
        subject=f"state:{hypothesis_id}:{state}",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_HYPOTHESIS_STATE,
        source="growth_strategy",
        user_id=str(user_id),
        payload={
            "hypothesis_id": str(hypothesis_id),
            "state": str(state),
            "note": str(note),
        },
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )


def append_experiment(
    event_store: Any,
    *,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    exp: ExperimentSpecV1,
) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    event_id = _event_id(
        tenant_id=str(tenant_id),
        decision_id=str(decision_id),
        event_type=GROWTH_EXPERIMENT_CREATED,
        subject=f"experiment:{exp.experiment_id}",
    )
    return _emit_once(
        log,
        event_id=event_id,
        event_type=GROWTH_EXPERIMENT_CREATED,
        source="growth_strategy",
        user_id=str(user_id),
        payload={"experiment": asdict(exp)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )


def list_hypotheses(event_store: Any, *, tenant_id: str, limit: int = 100) -> tuple[GrowthHypothesisV1, ...]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_CREATED,), limit=int(limit))
    out: list[GrowthHypothesisV1] = []
    for event in events:
        try:
            hypothesis = (event.get("payload") or {}).get("hypothesis") or {}
            out.append(GrowthHypothesisV1(**hypothesis))
        except Exception:
            continue
    return tuple(out)


def latest_scores(event_store: Any, *, tenant_id: str, limit: int = 250) -> dict[str, OpportunityScoreV1]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_SCORED,), limit=int(limit))
    result: dict[str, OpportunityScoreV1] = {}
    for event in events:
        try:
            score = (event.get("payload") or {}).get("score") or {}
            obj = OpportunityScoreV1(**score)
            if obj.hypothesis_id and obj.hypothesis_id not in result:
                result[obj.hypothesis_id] = obj
        except Exception:
            continue
    return result


def latest_states(event_store: Any, *, tenant_id: str, limit: int = 250) -> dict[str, str]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_STATE,), limit=int(limit))
    result: dict[str, str] = {}
    for event in events:
        try:
            payload = dict(event.get("payload") or {})
            hypothesis_id = str(payload.get("hypothesis_id") or "")
            state = str(payload.get("state") or "")
            if hypothesis_id and state and hypothesis_id not in result:
                result[hypothesis_id] = state
        except Exception:
            continue
    return result


def list_backlog(
    event_store: Any,
    *,
    tenant_id: str,
    limit: int = 100,
) -> tuple[tuple[GrowthHypothesisV1, OpportunityScoreV1 | None, str], ...]:
    hypotheses = list_hypotheses(event_store, tenant_id=tenant_id, limit=int(limit))
    scores = latest_scores(event_store, tenant_id=tenant_id, limit=int(limit) * 3)
    states = latest_states(event_store, tenant_id=tenant_id, limit=int(limit) * 3)

    return tuple(
        (hypothesis, scores.get(hypothesis.hypothesis_id), states.get(hypothesis.hypothesis_id, "new"))
        for hypothesis in hypotheses
    )


def _latest(event_store: Any, *, tenant_id: str, types: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        try:
            return list(latest(tenant_id=tenant_id, event_types=types, limit=int(limit)) or [])
        except Exception:
            return []
    iterator = getattr(event_store, "iter_events", None)
    if callable(iterator):
        try:
            return list(
                iterator(
                    tenant_id=tenant_id,
                    event_types=types,
                    start_ms=0,
                    end_ms=None,
                    limit=int(limit),
                )
                or []
            )
        except Exception:
            return []
    return []
