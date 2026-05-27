from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {'ctr_growth', 'engagement_growth', 'raw_revenue'}


def test_no_forbidden_objective_names_in_codebase():
    offenders = []
    for path in ROOT.rglob('*.py'):
        rel = str(path.relative_to(ROOT))
        if rel.startswith('tests/') or '__pycache__' in rel:
            continue
        text = path.read_text(encoding='utf-8')
        for item in FORBIDDEN:
            if item in text:
                offenders.append((rel, item))
    assert offenders == []
