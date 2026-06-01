from __future__ import annotations

from demand_feedback.routing_feedback_engine import RoutingFeedbackEngine


def test_routing_feedback_engine():
    payload = RoutingFeedbackEngine().build_feedback(request_id="r1", business_id="b1", outcome={"converted": True})
    assert payload["outcome_code"] == "converted"
