from demand_learning.causal_outcome_engine import CausalOutcomeEngine


def test_causal_outcome_engine_uses_latest_row_per_request() -> None:
    engine = CausalOutcomeEngine()
    rows = (
        {'request_id': 'r1', 'business_id': 'biz-1', 'converted': False, 'revenue': 0.0, 'outcome_updated_at_ms': 1},
        {'request_id': 'r1', 'business_id': 'biz-1', 'converted': True, 'revenue': 200.0, 'outcome_updated_at_ms': 2},
        {'request_id': 'r2', 'business_id': 'biz-2', 'converted': False, 'revenue': 0.0, 'outcome_updated_at_ms': 2},
        {'request_id': 'r3', 'business_id': 'biz-2', 'converted': False, 'revenue': 0.0, 'outcome_updated_at_ms': 3},
        {'request_id': 'r4', 'business_id': 'biz-2', 'converted': False, 'revenue': 0.0, 'outcome_updated_at_ms': 4},
    )
    uplift = engine.uplift_by_business(rows)
    assert 'biz-1' in uplift
