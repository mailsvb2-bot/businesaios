from growth.ads.scale_winner_detector import ScaleWinnerDetector
from growth.ads.budget_allocator import BudgetAllocator


def test_campaign_scaling_pipeline_builds_scaling_artifacts():
    winner = ScaleWinnerDetector().detect({'campaign_id': 'c1', 'score': 0.95})
    budget = BudgetAllocator().allocate({'amount': 200.0})
    assert winner['kind'] == 'scale_candidates'
    assert budget['kind'] == 'budget_allocation'
