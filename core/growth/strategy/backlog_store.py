from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from core.events.log import EventLog
from core.tenancy.scope import TenantScope

from .contracts import ExperimentSpecV1, GrowthHypothesisV1, GrowthSignalV1, OpportunityScoreV1
from .event_types import (
    GROWTH_EXPERIMENT_CREATED,
    GROWTH_HYPOTHESIS_CREATED,
    GROWTH_HYPOTHESIS_SCORED,
    GROWTH_HYPOTHESIS_STATE,
    GROWTH_STRATEGY_SNAPSHOT,
)


def now_ms() -> int:
    return int(time.time() * 1000)


def append_strategy_snapshot(event_store: Any, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, signals: GrowthSignalV1) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    ev = log.emit(
        user_id=str(user_id),
        source="growth_strategy",
        event_type=GROWTH_STRATEGY_SNAPSHOT,
        payload={"signals": asdict(signals)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )
    return str(ev.event_id)


def append_hypothesis(event_store: Any, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, h: GrowthHypothesisV1) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    ev = log.emit(
        user_id=str(user_id),
        source="growth_strategy",
        event_type=GROWTH_HYPOTHESIS_CREATED,
        payload={"hypothesis": asdict(h)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )
    return str(ev.event_id)


def append_score(event_store: Any, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, score: OpportunityScoreV1) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    ev = log.emit(
        user_id=str(user_id),
        source="growth_strategy",
        event_type=GROWTH_HYPOTHESIS_SCORED,
        payload={"score": asdict(score)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )
    return str(ev.event_id)


def set_hypothesis_state(event_store: Any, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, hypothesis_id: str, state: str, note: str = "") -> str:
    if state not in {"accepted", "rejected", "archived"}:
        raise ValueError("invalid_state")
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    ev = log.emit(
        user_id=str(user_id),
        source="growth_strategy",
        event_type=GROWTH_HYPOTHESIS_STATE,
        payload={"hypothesis_id": str(hypothesis_id), "state": str(state), "note": str(note)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )
    return str(ev.event_id)


def append_experiment(event_store: Any, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, exp: ExperimentSpecV1) -> str:
    log = EventLog(event_store, tenant=TenantScope(tenant_id))
    ev = log.emit(
        user_id=str(user_id),
        source="growth_strategy",
        event_type=GROWTH_EXPERIMENT_CREATED,
        payload={"experiment": asdict(exp)},
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        timestamp_ms=now_ms(),
    )
    return str(ev.event_id)


def list_hypotheses(event_store: Any, *, tenant_id: str, limit: int = 100) -> Tuple[GrowthHypothesisV1, ...]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_CREATED,), limit=int(limit))
    out: list[GrowthHypothesisV1] = []
    for e in events:
        try:
            h = (e.get("payload") or {}).get("hypothesis") or {}
            out.append(GrowthHypothesisV1(**h))
        except Exception:
            continue
    return tuple(out)


def latest_scores(event_store: Any, *, tenant_id: str, limit: int = 250) -> Dict[str, OpportunityScoreV1]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_SCORED,), limit=int(limit))
    m: Dict[str, OpportunityScoreV1] = {}
    for e in events:
        try:
            s = (e.get("payload") or {}).get("score") or {}
            obj = OpportunityScoreV1(**s)
            if obj.hypothesis_id and obj.hypothesis_id not in m:
                m[obj.hypothesis_id] = obj
        except Exception:
            continue
    return m


def latest_states(event_store: Any, *, tenant_id: str, limit: int = 250) -> Dict[str, str]:
    events = _latest(event_store, tenant_id=tenant_id, types=(GROWTH_HYPOTHESIS_STATE,), limit=int(limit))
    m: Dict[str, str] = {}
    for e in events:
        try:
            p = dict(e.get("payload") or {})
            hid = str(p.get("hypothesis_id") or "")
            st = str(p.get("state") or "")
            if hid and st and hid not in m:
                m[hid] = st
        except Exception:
            continue
    return m


def list_backlog(event_store: Any, *, tenant_id: str, limit: int = 100) -> Tuple[Tuple[GrowthHypothesisV1, Optional[OpportunityScoreV1], str], ...]:
    hs = list_hypotheses(event_store, tenant_id=tenant_id, limit=int(limit))
    scores = latest_scores(event_store, tenant_id=tenant_id, limit=int(limit) * 3)
    states = latest_states(event_store, tenant_id=tenant_id, limit=int(limit) * 3)

    out: list[Tuple[GrowthHypothesisV1, Optional[OpportunityScoreV1], str]] = []
    for h in hs:
        out.append((h, scores.get(h.hypothesis_id), states.get(h.hypothesis_id, "new")))
    return tuple(out)


def _latest(event_store: Any, *, tenant_id: str, types: Tuple[str, ...], limit: int) -> List[Dict[str, Any]]:
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        try:
            return list(latest(tenant_id=tenant_id, event_types=types, limit=int(limit)) or [])
        except Exception:
            return []
    it = getattr(event_store, "iter_events", None)
    if callable(it):
        try:
            return list(it(tenant_id=tenant_id, event_types=types, start_ms=0, end_ms=None, limit=int(limit)) or [])
        except Exception:
            return []
    return []
