from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_executable_action_is_only_constructed_in_decision_core_and_tests():
    offenders = []
    for path in ROOT.rglob('*.py'):
        rel = str(path.relative_to(ROOT))
        if rel.startswith('tests/') or '__pycache__' in rel:
            continue
        text = path.read_text()
        if 'ExecutableAction(' in text and rel != 'core/decision/decision_core.py':
            offenders.append(rel)
    assert offenders == []
