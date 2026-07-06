from __future__ import annotations

from dataclasses import dataclass, field

from runtime.state.state_contract import StateObservation

CANON_STATE_FRESHNESS_POLICY = True


@dataclass(frozen=True)
class FieldFreshnessPolicy:
    ttl_ms: int | None = None
    max_future_skew_ms: int = 60_000
    allow_stale_if_authoritative: bool = True


@dataclass(frozen=True)
class FreshnessDecision:
    status: str
    reason: str
    effective_ttl_ms: int | None
    age_ms: int


@dataclass(frozen=True)
class StateFreshnessPolicy:
    default_ttl_ms: int | None = 3_600_000
    default_max_future_skew_ms: int = 60_000
    field_policies: dict[str, FieldFreshnessPolicy] = field(default_factory=dict)
    prefix_policies: dict[str, FieldFreshnessPolicy] = field(default_factory=dict)

    def policy_for(self, field_path: str) -> FieldFreshnessPolicy:
        if field_path in self.field_policies:
            return self.field_policies[field_path]

        best_prefix = ""
        best_policy: FieldFreshnessPolicy | None = None
        for prefix, policy in self.prefix_policies.items():
            normalized = str(prefix).strip(".")
            if not normalized:
                continue
            if (field_path == normalized or field_path.startswith(normalized + ".")) and len(normalized) > len(best_prefix):
                best_prefix = normalized
                best_policy = policy

        if best_policy is not None:
            return best_policy

        return FieldFreshnessPolicy(
            ttl_ms=self.default_ttl_ms,
            max_future_skew_ms=self.default_max_future_skew_ms,
            allow_stale_if_authoritative=True,
        )

    def evaluate(self, *, now_ms: int, observation: StateObservation) -> FreshnessDecision:
        policy = self.policy_for(str(observation.field_path))
        effective_ttl_ms = observation.ttl_ms if observation.ttl_ms is not None else policy.ttl_ms
        observed_at_ms = int(observation.observed_at_ms)
        age_ms = int(now_ms) - observed_at_ms

        if age_ms < 0:
            if abs(age_ms) > int(policy.max_future_skew_ms):
                return FreshnessDecision(
                    status="invalid_future",
                    reason="future_skew_exceeded",
                    effective_ttl_ms=effective_ttl_ms,
                    age_ms=age_ms,
                )
            return FreshnessDecision(
                status="fresh",
                reason="future_skew_within_tolerance",
                effective_ttl_ms=effective_ttl_ms,
                age_ms=age_ms,
            )

        if effective_ttl_ms is None:
            return FreshnessDecision(
                status="fresh",
                reason="ttl_unbounded",
                effective_ttl_ms=None,
                age_ms=age_ms,
            )

        if age_ms <= int(effective_ttl_ms):
            return FreshnessDecision(
                status="fresh",
                reason="within_ttl",
                effective_ttl_ms=int(effective_ttl_ms),
                age_ms=age_ms,
            )

        if bool(observation.authoritative) and bool(policy.allow_stale_if_authoritative):
            return FreshnessDecision(
                status="stale_authoritative",
                reason="beyond_ttl_but_authoritative",
                effective_ttl_ms=int(effective_ttl_ms),
                age_ms=age_ms,
            )

        return FreshnessDecision(
            status="stale",
            reason="beyond_ttl",
            effective_ttl_ms=int(effective_ttl_ms),
            age_ms=age_ms,
        )
