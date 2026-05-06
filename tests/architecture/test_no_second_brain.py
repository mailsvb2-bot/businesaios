from pathlib import Path
from canon.anti_second_brain_rules import FORBIDDEN_DECISION_CLASS_NAMES


ROOT = Path(__file__).resolve().parents[2]


def test_second_brain_names_forbidden():
    assert 'SecondDecisionCore' in FORBIDDEN_DECISION_CLASS_NAMES


def test_no_forbidden_class_names_in_codebase():
    for path in ROOT.rglob('*.py'):
        if '__pycache__' in str(path):
            continue
        text = path.read_text()
        for forbidden in FORBIDDEN_DECISION_CLASS_NAMES:
            assert f'class {forbidden}' not in text
