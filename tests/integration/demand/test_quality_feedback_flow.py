from __future__ import annotations

from demand_feedback.quality_feedback_engine import QualityFeedbackEngine
from quality.business_quality_engine import BusinessQualityEngine


def test_quality_feedback_flow():
    snapshot = BusinessQualityEngine().evaluate(business_id="b1", outcome={"responded": True, "converted": False})
    payload = QualityFeedbackEngine().summarize(snapshot)
    assert "quality_score" in payload
