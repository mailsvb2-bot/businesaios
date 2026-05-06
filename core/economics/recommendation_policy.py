from __future__ import annotations

from application.decisioning.decision_output_guard import assert_non_decision_payload
from kernel.decisioning.decision_types import RecommendationSet


def ensure_economics_recommendations(value: object) -> RecommendationSet:
    return assert_non_decision_payload(value)
