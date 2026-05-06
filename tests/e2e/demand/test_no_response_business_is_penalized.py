from __future__ import annotations

from quality.business_quality_engine import BusinessQualityEngine

def test_no_response_business_is_penalized():
    bad = BusinessQualityEngine().evaluate(business_id="b1", outcome={"responded": False, "converted": False})
    good = BusinessQualityEngine().evaluate(business_id="b1", outcome={"responded": True, "converted": False})
    assert bad.quality_score < good.quality_score
