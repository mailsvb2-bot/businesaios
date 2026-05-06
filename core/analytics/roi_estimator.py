from __future__ import annotations

from dataclasses import dataclass, field

from config.roi_estimator_policy import ROIEstimatorPolicy


@dataclass(frozen=True)
class ROIEstimate:
    expected_uplift_pct: float
    expected_delta_revenue: float
    confidence: float


@dataclass(frozen=True)
class SimpleROIEstimator:
    """Stable, non-LLM ROI estimate with capped uplift."""

    max_uplift_pct: float | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    policy: ROIEstimatorPolicy = field(default_factory=ROIEstimatorPolicy)

    def __post_init__(self) -> None:
        policy = self.policy
        if self.max_uplift_pct is None:
            object.__setattr__(self, "max_uplift_pct", float(policy.max_uplift_pct))
        if self.min_confidence is None:
            object.__setattr__(self, "min_confidence", float(policy.min_confidence))
        if self.max_confidence is None:
            object.__setattr__(self, "max_confidence", float(policy.max_confidence))

    def estimate(self, *, baseline_revenue: float, action: str, impressions: int, clicks: int) -> ROIEstimate:
        policy = self.policy
        if impressions < policy.low_impressions_threshold:
            conf = float(self.min_confidence)
        elif impressions < policy.medium_impressions_threshold:
            conf = float(policy.medium_confidence)
        else:
            conf = float(self.max_confidence)

        uplift = float(policy.default_uplift_pct)
        if action == "increase_impressions":
            uplift = float(policy.increase_impressions_uplift_pct)
        elif action == "improve_ctr":
            uplift = float(policy.improve_ctr_uplift_pct)
        elif action == "improve_cr":
            uplift = float(policy.improve_cr_uplift_pct)
        elif action == "double_winner":
            uplift = float(policy.double_winner_uplift_pct)

        uplift = max(float(), min(float(self.max_uplift_pct), float(uplift)))
        delta = float(baseline_revenue) * uplift
        return ROIEstimate(expected_uplift_pct=uplift, expected_delta_revenue=delta, confidence=float(conf))
