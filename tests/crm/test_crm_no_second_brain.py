from pathlib import Path


def test_crm_decision_integration_contains_only_signals():
    for path in Path('decision_integrations/crm').glob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert 'DecisionCore(' not in text
        assert '.decide(' not in text
