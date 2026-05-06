from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


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
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
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


class CapabilityHealthPolicy:
    def __init__(
        self,
        *,
        stale_after_hours: float = 72.0,
        cooling_after_hours: float = 24.0,
        low_confidence_threshold: float = 0.35,
        sufficient_evidence_attempts: int = 3,
    ) -> None:
        self._stale_after_hours = float(stale_after_hours)
        self._cooling_after_hours = float(cooling_after_hours)
        self._low_confidence_threshold = float(low_confidence_threshold)
        self._sufficient_evidence_attempts = int(max(1, sufficient_evidence_attempts))

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
        now = now_utc or datetime.now(timezone.utc)
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
        if tier == 'unknown':
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
        )


__all__ = ['CANON_CAPABILITY_HEALTH_POLICY', 'CapabilityHealthPolicy', 'CapabilityHealthPolicyView']
