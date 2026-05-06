from __future__ import annotations

from quality.business_quality_engine import BusinessQualityEngine

def test_business_quality_engine():
    snapshot = BusinessQualityEngine().evaluate(business_id="b1", outcome={"responded": True, "converted": True, "revenue": 100.0})
    assert 0.0 <= snapshot.quality_score <= 1.0
