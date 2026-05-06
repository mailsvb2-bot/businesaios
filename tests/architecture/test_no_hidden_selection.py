from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_LOCAL_SELECTORS = {
    'core/decision/decision_selector.py',
    'growth/ads/bid_strategy_selector.py',
    'growth/ads/channel_selector.py',
    'growth/budget_engine.py',
    'growth/campaign_engine.py',
    'growth/creative_engine.py',
    'growth/landing/landing_layout_selector.py',
}


def test_no_hidden_selection_methods_outside_allowed_modules():
    offenders = []
    for path in ROOT.rglob('*.py'):
        rel = str(path.relative_to(ROOT))
        if '__pycache__' in rel or rel.startswith('tests/'):
            continue
        text = path.read_text()
        if 'def select(' in text and rel not in ALLOWED_LOCAL_SELECTORS and 'marketplace/' not in rel:
            offenders.append(rel)
    assert offenders == []
