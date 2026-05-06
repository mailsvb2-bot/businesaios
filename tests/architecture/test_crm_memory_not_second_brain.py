from pathlib import Path


def test_crm_memory_never_exposes_decision_entrypoints():
    for path in Path('crm/memory').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert 'decide(' not in text
        assert 'DecisionCore' not in text
