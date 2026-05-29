from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from config.growth_trust_policy import DEFAULT_GROWTH_TRUST_POLICY, GrowthTrustPolicy


class EventStore(Protocol):
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 2000) -> Iterable[dict[str, Any]]: ...


@dataclass
class Trust:
    score: float = field(default_factory=lambda: float(DEFAULT_GROWTH_TRUST_POLICY.initial_score))


class TrustScore:
    def __init__(self, store: EventStore, policy: GrowthTrustPolicy = DEFAULT_GROWTH_TRUST_POLICY):
        self._store = store
        self._policy = policy

    def _event_count(self, *, tenant_id: str, event_type: str) -> int:
        return len(
            list(
                self._store.latest_events(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    limit=self._policy.event_limit,
                )
            )
        )

    def get(self, *, tenant_id: str) -> Trust:
        policy = self._policy
        score = float(policy.initial_score)
        score += float(policy.success_weight) * self._event_count(
            tenant_id=tenant_id,
            event_type="ads_reco_apply_success",
        )
        score -= float(policy.failure_weight) * self._event_count(
            tenant_id=tenant_id,
            event_type="ads_reco_apply_failed",
        )
        score -= float(policy.blocked_weight) * self._event_count(
            tenant_id=tenant_id,
            event_type="ads_reco_apply_blocked",
        )
        score = max(float(policy.min_score), min(float(policy.max_score), score))
        return Trust(score=score)

    def allow_autopilot(self, *, tenant_id: str, threshold: float | None = None) -> bool:
        target_threshold = self._policy.autopilot_threshold if threshold is None else threshold
        return self.get(tenant_id=tenant_id).score >= float(target_threshold)
