from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

CANON_CAPABILITY_HEALTH_POLICY = True



def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)



def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))



def _parse_ts(value: object) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if text.endswith('Z'):
            return datetime.fromisoformat(text[:-1] + '+00:00')
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


@dataclass(frozen=True)
class CapabilityHealthPolicyView:
    success_rate: float
    verification_rate: float
    transient_failure_rate: float
    block_rate: float
    health_score: float
    health_tier: str
    degraded: bool
    routing_state: str
    confidence_score: float = 0.0
    staleness_state: str = 'unknown'
    evidence_state: str = 'insufficient'
    freshness_score: float = 0.0
    recommended_autonomy_tier: str = 'supervised'
    error_budget_used: float = 0.0
    error_budget_limit: float = 0.0
    error_budget_exceeded: bool = False
    accumulated_risk: float = 0.0
    risk_budget_limit: float = 0.0
    risk_budget_exceeded: bool = False


class CapabilityHealthPolicy:
    def __init__(
        self,
        *,
        stale_after_hours: float = 72.0,
        cooling_after_hours: float = 24.0,
        low_confidence_threshold: float = 0.35,
        sufficient_evidence_attempts: int = 3,
        error_budget_limit: float = 3.0,
        transient_failure_weight: float = 0.25,
        risk_budget_limit: float = 3.0,
    ) -> None:
        self._stale_after_hours = float(stale_after_hours)
        self._cooling_after_hours = float(cooling_after_hours)
        self._low_confidence_threshold = float(low_confidence_threshold)
        self._sufficient_evidence_attempts = int(max(1, sufficient_evidence_attempts))
        self._error_budget_limit = max(0.0, float(error_budget_limit))
        self._transient_failure_weight = max(0.0, float(transient_failure_weight))
        self._risk_budget_limit = max(0.0, float(risk_budget_limit))

    def tier(self, score: float) -> str:
        if score >= 0.80:
            return 'healthy'
        if score >= 0.50:
            return 'degraded'
        if score > 0.0:
            return 'unhealthy'
        return 'unknown'

    def _freshness(self, *, updated_at: object, now_utc: datetime | None) -> tuple[str, float]:
        observed_at = _parse_ts(updated_at)
        if observed_at is None:
            return 'unknown', 0.0
        now = now_utc or datetime.now(UTC)
        age_seconds = max(0.0, (now - observed_at).total_seconds())
        if age_seconds >= self._stale_after_hours * 3600.0:
            return 'stale', 0.10
        if age_seconds >= self._cooling_after_hours * 3600.0:
            return 'cooling', 0.55
        return 'fresh', 1.0

    def build_view(
        self,
        *,
        counters: Mapping[str, Any],
        updated_at: object | None = None,
        now_utc: datetime | None = None,
    ) -> CapabilityHealthPolicyView:
        attempts = max(0.0, _safe_float(counters.get('attempts')))
        executed = max(0.0, _safe_float(counters.get('executed')))
        verified = max(0.0, _safe_float(counters.get('verified')))
        transient_failures = max(0.0, _safe_float(counters.get('transient_failures')))
        blocked = max(0.0, _safe_float(counters.get('blocked')))
        terminal_failures = max(0.0, _safe_float(counters.get('terminal_failures')))

        success_rate = _ratio(executed, attempts)
        verification_rate = _ratio(verified, executed)
        transient_failure_rate = _ratio(transient_failures, attempts)
        block_rate = _ratio(blocked, attempts)
        terminal_failure_rate = _ratio(terminal_failures, attempts)
        error_budget_used = terminal_failures + (transient_failures * self._transient_failure_weight)
        accumulated_risk = max(0.0, _safe_float(counters.get('accumulated_risk')))
        error_budget_exceeded = (
            self._error_budget_limit > 0.0
            and error_budget_used > self._error_budget_limit
        )
        risk_budget_exceeded = (
            self._risk_budget_limit > 0.0
            and accumulated_risk > self._risk_budget_limit
        )

        staleness_state, freshness_score = self._freshness(updated_at=updated_at, now_utc=now_utc)
        evidence_coverage = min(1.0, attempts / float(self._sufficient_evidence_attempts))
        confidence_score = max(
            0.0,
            min(
                1.0,
                (evidence_coverage * 0.45)
                + (verification_rate * 0.35)
                + (success_rate * 0.10)
                + (freshness_score * 0.10),
            ),
        )

        health_score = max(
            0.0,
            min(
                1.0,
                (success_rate * 0.30)
                + (verification_rate * 0.30)
                + ((1.0 - transient_failure_rate) * 0.10)
                + ((1.0 - block_rate) * 0.10)
                + ((1.0 - terminal_failure_rate) * 0.10)
                + (freshness_score * 0.10),
            ),
        )
        tier = self.tier(health_score)

        if attempts <= 0.0:
            evidence_state = 'unknown'
        elif attempts < float(self._sufficient_evidence_attempts) or confidence_score < self._low_confidence_threshold:
            evidence_state = 'insufficient'
        else:
            evidence_state = 'sufficient'

        routing_state = 'enabled'
        recommended_autonomy_tier = 'full_autonomy'
        if error_budget_exceeded or risk_budget_exceeded:
            routing_state = 'fallback_preferred'
            recommended_autonomy_tier = 'supervised'
        elif tier == 'unknown':
            routing_state = 'observe'
            recommended_autonomy_tier = 'supervised'
        elif tier == 'unhealthy':
            routing_state = 'fallback_preferred'
            recommended_autonomy_tier = 'supervised'
        elif staleness_state == 'stale':
            routing_state = 'fallback_preferred'
            recommended_autonomy_tier = 'bounded_autonomy'
        elif staleness_state == 'cooling' or evidence_state == 'insufficient':
            routing_state = 'observe'
            recommended_autonomy_tier = 'bounded_autonomy'
        elif tier == 'degraded':
            recommended_autonomy_tier = 'bounded_autonomy'

        return CapabilityHealthPolicyView(
            success_rate=success_rate,
            verification_rate=verification_rate,
            transient_failure_rate=transient_failure_rate,
            block_rate=block_rate,
            health_score=health_score,
            health_tier=tier,
            degraded=tier == 'degraded' or staleness_state in {'stale', 'cooling'},
            routing_state=routing_state,
            confidence_score=confidence_score,
            staleness_state=staleness_state,
            evidence_state=evidence_state,
            freshness_score=freshness_score,
            recommended_autonomy_tier=recommended_autonomy_tier,
            error_budget_used=error_budget_used,
            error_budget_limit=self._error_budget_limit,
            error_budget_exceeded=error_budget_exceeded,
            accumulated_risk=accumulated_risk,
            risk_budget_limit=self._risk_budget_limit,
            risk_budget_exceeded=risk_budget_exceeded,
        )


__all__ = ['CANON_CAPABILITY_HEALTH_POLICY', 'CapabilityHealthPolicy', 'CapabilityHealthPolicyView']
