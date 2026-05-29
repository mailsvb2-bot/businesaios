from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping, Sequence

from core.contracts.business_scorecard import (
    AnalyticsDiagnosis,
    BusinessScorecard,
    DecisionSnapshot,
    FunnelSnapshot,
    LatencySnapshot,
    RetentionSnapshot,
    RevenueSnapshot,
)
from core.events import event_types as et


@dataclass(frozen=True)
class BusinessAnalyticsPolicy:
    default_window_days: int = 30
    low_conversion_warn_ratio: float = 0.02
    low_retention_warn_ratio: float = 0.15
    blocked_decision_warn_ratio: float = 0.10
    default_latency_budget_ms: int = 1500
    degraded_latency_budget_ms: int = 3000
    score_good_threshold: float = 0.80
    score_warn_threshold: float = 0.55


DEFAULT_POLICY = BusinessAnalyticsPolicy()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return int(default)
        if isinstance(value, str) and 'T' in value:
            return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000)
        return int(float(value))
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _ratio(n: int | float, d: int | float, digits: int = 4) -> float:
    if float(d) <= 0.0:
        return 0.0
    return round(float(n) / float(d), digits)


def _percentile(values: Sequence[int], q: float) -> int:
    if not values:
        return 0
    if len(values) == 1:
        return int(values[0])
    idx = (len(values) - 1) * float(q)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return int(values[lo])
    return int(round(values[lo] * (hi - idx) + values[hi] * (idx - lo)))


def _normalize_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, Mapping):
            continue
        payload = item.get('payload') if isinstance(item.get('payload'), Mapping) else {}
        out.append(
            {
                'event_type': str(item.get('event_type') or item.get('type') or ''),
                'timestamp_ms': _safe_int(item.get('timestamp_ms') or item.get('ts_ms') or item.get('ts')),
                'user_id': None if item.get('user_id') in (None, '', 'system') else str(item.get('user_id')),
                'payload': dict(payload),
            }
        )
    return out


@dataclass(frozen=True)
class BusinessAnalyticsService:
    policy: BusinessAnalyticsPolicy = DEFAULT_POLICY

    def build_scorecard(
        self,
        *,
        tenant_id: str,
        events: Iterable[Mapping[str, Any]],
        window_days: int | None = None,
        generated_at_ms: int | None = None,
    ) -> BusinessScorecard:
        normalized = _normalize_events(events)
        generated = int(generated_at_ms or int(time.time() * 1000))
        resolved_days = int(window_days or self.policy.default_window_days)

        users = {e['user_id'] for e in normalized if e.get('user_id')}
        shown = len({e['user_id'] for e in normalized if e.get('user_id') and e['event_type'] == et.OFFER_SHOWN})
        clicked = len({e['user_id'] for e in normalized if e.get('user_id') and e['event_type'] == et.OFFER_CLICKED})
        attempted = len({e['user_id'] for e in normalized if e.get('user_id') and e['event_type'] == et.PURCHASE_ATTEMPT})
        success_users = {e['user_id'] for e in normalized if e.get('user_id') and e['event_type'] == et.PURCHASE_SUCCESS}
        success_count = sum(1 for e in normalized if e['event_type'] == et.PURCHASE_SUCCESS)
        failed_count = sum(1 for e in normalized if e['event_type'] == et.PURCHASE_FAILED)
        revenue_total = round(sum(_safe_float(e['payload'].get('amount')) for e in normalized if e['event_type'] == et.PURCHASE_SUCCESS), 2)
        issued = sum(1 for e in normalized if e['event_type'] == et.DECISION_ISSUED)
        executed = sum(1 for e in normalized if e['event_type'] == et.DECISION_EXECUTED)
        blocked = sum(1 for e in normalized if e['event_type'] == et.DECISION_BLOCKED)

        per_user_days: dict[str, set[str]] = {}
        for e in normalized:
            if not e.get('user_id') or e['timestamp_ms'] <= 0:
                continue
            day = datetime.fromtimestamp(e['timestamp_ms'] / 1000.0, tz=UTC).strftime('%Y-%m-%d')
            per_user_days.setdefault(str(e['user_id']), set()).add(day)
        active_users = len(per_user_days)
        returning_users = sum(1 for ds in per_user_days.values() if len(ds) >= 2)

        samples = sorted(
            _safe_int(e['payload'].get('duration_ms'))
            for e in normalized
            if e['event_type'] == 'latency_span' and _safe_int(e['payload'].get('duration_ms')) > 0
        )
        p50 = _percentile(samples, 0.50)
        p95 = _percentile(samples, 0.95)
        p99 = _percentile(samples, 0.99)
        if not samples:
            latency_state = 'unknown'
        elif p95 <= self.policy.default_latency_budget_ms:
            latency_state = 'healthy'
        elif p95 <= self.policy.degraded_latency_budget_ms:
            latency_state = 'degraded'
        else:
            latency_state = 'critical'

        funnel = FunnelSnapshot(
            visitors=len(users),
            offer_shown=shown,
            offer_clicked=clicked,
            purchase_attempt=attempted,
            purchase_success=len(success_users),
            offer_ctr=_ratio(clicked, shown),
            purchase_rate_from_click=_ratio(len(success_users), clicked),
            visitor_to_purchase_rate=_ratio(len(success_users), max(len(users), 1)),
        )
        revenue = RevenueSnapshot(
            purchase_success_count=success_count,
            purchase_failed_count=failed_count,
            revenue_total=revenue_total,
            average_order_value=round(revenue_total / success_count, 2) if success_count else 0.0,
        )
        retention = RetentionSnapshot(
            active_users=active_users,
            returning_users=returning_users,
            retention_ratio=_ratio(returning_users, active_users),
            churn_ratio=round(max(0.0, 1.0 - _ratio(returning_users, active_users)), 4),
        )
        decisions = DecisionSnapshot(
            issued_count=issued,
            executed_count=executed,
            blocked_count=blocked,
            execution_ratio=_ratio(executed, max(issued, 1)),
            blocked_ratio=_ratio(blocked, max(issued, 1)),
        )
        latency = LatencySnapshot(
            sample_count=len(samples),
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            health_state=latency_state,
        )
        diagnosis = self._diagnose(funnel=funnel, retention=retention, decisions=decisions, latency=latency, revenue=revenue)
        return BusinessScorecard(
            tenant_id=str(tenant_id),
            window_days=resolved_days,
            traffic_users=len(users),
            funnel=funnel,
            revenue=revenue,
            retention=retention,
            decisions=decisions,
            latency=latency,
            diagnosis=diagnosis,
            generated_at_ms=generated,
            metadata={'analytics_owner': 'core.analytics.business_scorecard'},
        )

    def _diagnose(
        self,
        *,
        funnel: FunnelSnapshot,
        retention: RetentionSnapshot,
        decisions: DecisionSnapshot,
        latency: LatencySnapshot,
        revenue: RevenueSnapshot,
    ) -> AnalyticsDiagnosis:
        reasons: list[str] = []
        highlights: list[str] = []
        score = 1.0
        if funnel.offer_shown > 0 and funnel.offer_ctr < self.policy.low_conversion_warn_ratio:
            reasons.append('low_offer_ctr')
            score -= 0.12
        else:
            highlights.append('offer_ctr_not_collapsed')
        if retention.active_users > 0 and retention.retention_ratio < self.policy.low_retention_warn_ratio:
            reasons.append('low_retention')
            score -= 0.15
        else:
            if retention.returning_users > 0:
                highlights.append('returning_users_present')
        if decisions.blocked_ratio > self.policy.blocked_decision_warn_ratio:
            reasons.append('high_blocked_decision_ratio')
            score -= 0.15
        else:
            if decisions.executed_count > 0:
                highlights.append('execution_path_operational')
        if latency.health_state == 'degraded':
            reasons.append('latency_degraded')
            score -= 0.10
        elif latency.health_state == 'critical':
            reasons.append('latency_critical')
            score -= 0.20
        elif latency.health_state == 'healthy':
            highlights.append('latency_within_budget')
        if revenue.purchase_success_count > 0:
            highlights.append('revenue_signal_present')
        else:
            reasons.append('low_revenue_signal')
            score -= 0.08
        score = max(0.0, min(1.0, round(score, 4)))
        state = 'healthy' if score >= self.policy.score_good_threshold else 'warning' if score >= self.policy.score_warn_threshold else 'critical'
        if not reasons:
            reasons.append('no_major_issues_detected')
        return AnalyticsDiagnosis(overall_state=state, score=score, reasons=reasons, highlights=highlights)
