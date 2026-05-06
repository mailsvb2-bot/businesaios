from pathlib import Path


SCAN_ROOTS = ['crm', 'runtime', 'decision_integrations/crm']


def test_no_direct_decision_core_calls_inside_crm_contour():
    for root in SCAN_ROOTS:
        for path in Path(root).rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            assert '.decide(' not in text
