from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_executable_action_is_only_constructed_in_sovereign_decision_core_and_tests():
    offenders = []
    canonical_owner = 'core/ai/decision_core.py'
    for path in ROOT.rglob('*.py'):
        rel = str(path.relative_to(ROOT))
        if rel.startswith('tests/') or '__pycache__' in rel:
            continue
        text = path.read_text()
        if 'ExecutableAction(' in text and rel != canonical_owner:
            offenders.append(rel)
    assert offenders == []
    owner_text = (ROOT / canonical_owner).read_text()
    assert 'CANON_EXECUTABLE_ACTION_PROJECTION_OWNER = True' in owner_text
    assert 'def project_executable_action(' in owner_text
