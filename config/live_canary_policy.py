from __future__ import annotations

import math
import os
from dataclasses import dataclass


def _csv(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, "").split(",") if item.strip())


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


@dataclass(frozen=True)
class LiveCanaryPolicy:
    """Fail-closed configuration for one randomized live business experiment."""

    enabled: bool = False
    experiment_id: str = ""
    candidate_policy_id: str = ""
    assignment_secret: str = ""
    candidate_pct: float = 0.0
    max_candidate_pct: float = 1.0
    initial_canary_pct: int = 1
    allowed_tenant_ids: tuple[str, ...] = ()
    allowed_purposes: tuple[str, ...] = ("live_canary",)
    eligibility_state_key: str = "live_canary_eligible"
    allowed_actions: tuple[str, ...] = ("send_message@v1",)
    outcome_event_types: tuple[str, ...] = (
        "booking_confirmed@v1",
        "payment_succeeded",
        "purchase_success",
    )
    max_candidate_actions_per_day: int = 50
    max_candidate_actions_per_subject_24h: int = 1
    max_daily_cost: float = 100.0
    max_error_rate: float = 0.05
    max_critical_violations: int = 0
    max_complaint_rate: float = 0.01
    max_cost_per_outcome_ratio: float = 1.25
    max_relative_conversion_drop: float = 0.05
    max_sample_ratio_z: float = 4.0
    min_assignments: int = 1000
    min_candidate_assignments: int = 10
    min_outcomes_per_arm: int = 10
    min_duration_seconds: int = 72 * 60 * 60
    outcome_window_seconds: int = 72 * 60 * 60
    outcome_poll_seconds: float = 5.0

    @property
    def candidate_fraction(self) -> float:
        return max(0.0, min(1.0, float(self.candidate_pct) / 100.0))

    def validate(self) -> tuple[str, ...]:
        issues: list[str] = []
        if not self.enabled:
            return ()
        if not self.experiment_id.strip():
            issues.append("experiment_id_required")
        if len(self.assignment_secret.encode("utf-8")) < 32:
            issues.append("assignment_secret_must_be_at_least_32_bytes")
        if not _finite(self.candidate_pct) or not 0.0 < float(self.candidate_pct) <= 100.0:
            issues.append("candidate_pct_out_of_range")
        if not _finite(self.max_candidate_pct) or not 0.0 < float(self.max_candidate_pct) <= 100.0:
            issues.append("max_candidate_pct_out_of_range")
        if _finite(self.candidate_pct) and _finite(self.max_candidate_pct) and float(self.candidate_pct) > float(self.max_candidate_pct):
            issues.append("candidate_pct_exceeds_maximum")
        if not 0 < int(self.initial_canary_pct) <= 100:
            issues.append("initial_canary_pct_out_of_range")
        elif _finite(self.max_candidate_pct) and float(self.initial_canary_pct) > float(self.max_candidate_pct):
            issues.append("initial_canary_pct_exceeds_maximum")
        if not self.allowed_tenant_ids:
            issues.append("allowed_tenant_ids_required")
        if not self.allowed_purposes:
            issues.append("allowed_purposes_required")
        if not self.eligibility_state_key.strip():
            issues.append("eligibility_state_key_required")
        if not self.allowed_actions:
            issues.append("allowed_actions_required")
        if self.max_candidate_actions_per_day < 1:
            issues.append("max_candidate_actions_per_day_must_be_positive")
        if self.max_candidate_actions_per_subject_24h < 1:
            issues.append("max_candidate_actions_per_subject_24h_must_be_positive")
        if not _finite(self.max_daily_cost) or self.max_daily_cost < 0:
            issues.append("max_daily_cost_must_be_non_negative")
        if not _finite(self.max_error_rate) or not 0 <= self.max_error_rate <= 1:
            issues.append("max_error_rate_out_of_range")
        if not _finite(self.max_complaint_rate) or not 0 <= self.max_complaint_rate <= 1:
            issues.append("max_complaint_rate_out_of_range")
        if not _finite(self.max_cost_per_outcome_ratio) or self.max_cost_per_outcome_ratio < 1:
            issues.append("max_cost_per_outcome_ratio_must_be_at_least_one")
        if not _finite(self.max_relative_conversion_drop) or not 0 <= self.max_relative_conversion_drop < 1:
            issues.append("max_relative_conversion_drop_out_of_range")
        if not _finite(self.max_sample_ratio_z) or self.max_sample_ratio_z <= 0:
            issues.append("max_sample_ratio_z_must_be_positive")
        if self.min_assignments < 1 or self.min_candidate_assignments < 1:
            issues.append("minimum_assignment_counts_must_be_positive")
        if self.min_outcomes_per_arm < 1:
            issues.append("min_outcomes_per_arm_must_be_positive")
        if self.min_duration_seconds < 0 or self.outcome_window_seconds < 1:
            issues.append("invalid_time_window")
        if not _finite(self.outcome_poll_seconds) or self.outcome_poll_seconds < 1:
            issues.append("outcome_poll_seconds_must_be_at_least_one")
        return tuple(issues)

    def assert_valid(self) -> None:
        issues = self.validate()
        if issues:
            raise ValueError("invalid live canary policy: " + ",".join(issues))

    @classmethod
    def from_env(cls) -> "LiveCanaryPolicy":
        outcome_window = int(
            os.getenv("LIVE_CANARY_OUTCOME_WINDOW_SECONDS", str(72 * 60 * 60))
        )
        candidate_pct = float(os.getenv("LIVE_CANARY_CANDIDATE_PCT", "0"))
        return cls(
            enabled=_bool("LIVE_CANARY_ENABLED", False),
            experiment_id=os.getenv("LIVE_CANARY_EXPERIMENT_ID", "").strip(),
            candidate_policy_id=os.getenv(
                "LIVE_CANARY_CANDIDATE_POLICY_ID", ""
            ).strip(),
            assignment_secret=os.getenv("LIVE_CANARY_ASSIGNMENT_SECRET", ""),
            candidate_pct=candidate_pct,
            max_candidate_pct=float(
                os.getenv("LIVE_CANARY_MAX_CANDIDATE_PCT", str(candidate_pct or 1.0))
            ),
            initial_canary_pct=int(os.getenv("LIVE_CANARY_INITIAL_PCT", "1")),
            allowed_tenant_ids=_csv("LIVE_CANARY_TENANTS"),
            allowed_purposes=_csv("LIVE_CANARY_PURPOSES") or ("live_canary",),
            eligibility_state_key=os.getenv(
                "LIVE_CANARY_ELIGIBILITY_STATE_KEY", "live_canary_eligible"
            ).strip(),
            allowed_actions=_csv("LIVE_CANARY_ALLOWED_ACTIONS")
            or ("send_message@v1",),
            outcome_event_types=_csv("LIVE_CANARY_OUTCOME_EVENTS")
            or ("booking_confirmed@v1", "payment_succeeded", "purchase_success"),
            max_candidate_actions_per_day=int(
                os.getenv("LIVE_CANARY_MAX_ACTIONS_PER_DAY", "50")
            ),
            max_candidate_actions_per_subject_24h=int(
                os.getenv("LIVE_CANARY_MAX_ACTIONS_PER_SUBJECT_24H", "1")
            ),
            max_daily_cost=float(os.getenv("LIVE_CANARY_MAX_DAILY_COST", "100")),
            max_error_rate=float(os.getenv("LIVE_CANARY_MAX_ERROR_RATE", "0.05")),
            max_critical_violations=int(
                os.getenv("LIVE_CANARY_MAX_CRITICAL_VIOLATIONS", "0")
            ),
            max_complaint_rate=float(
                os.getenv("LIVE_CANARY_MAX_COMPLAINT_RATE", "0.01")
            ),
            max_cost_per_outcome_ratio=float(
                os.getenv("LIVE_CANARY_MAX_COST_PER_OUTCOME_RATIO", "1.25")
            ),
            max_relative_conversion_drop=float(
                os.getenv("LIVE_CANARY_MAX_RELATIVE_CONVERSION_DROP", "0.05")
            ),
            max_sample_ratio_z=float(
                os.getenv("LIVE_CANARY_MAX_SAMPLE_RATIO_Z", "4")
            ),
            min_assignments=int(os.getenv("LIVE_CANARY_MIN_ASSIGNMENTS", "1000")),
            min_candidate_assignments=int(
                os.getenv("LIVE_CANARY_MIN_CANDIDATE_ASSIGNMENTS", "10")
            ),
            min_outcomes_per_arm=int(
                os.getenv("LIVE_CANARY_MIN_OUTCOMES_PER_ARM", "10")
            ),
            min_duration_seconds=int(
                os.getenv("LIVE_CANARY_MIN_DURATION_SECONDS", str(outcome_window))
            ),
            outcome_window_seconds=outcome_window,
            outcome_poll_seconds=float(
                os.getenv("LIVE_CANARY_OUTCOME_POLL_SECONDS", "5")
            ),
        )


DEFAULT_LIVE_CANARY_POLICY = LiveCanaryPolicy.from_env()

__all__ = ["DEFAULT_LIVE_CANARY_POLICY", "LiveCanaryPolicy"]
