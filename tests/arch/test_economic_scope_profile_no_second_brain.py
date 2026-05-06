from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    'execution/economic_scope_profile.py',
]
FORBIDDEN_TOKENS = [
    'class DecisionCore',
    'RuntimeDecisionCore',
    'def decide(',
    'def issue(',
    'from core.ai.decision_core import DecisionCore',
    'from core.decision_core import DecisionCore',
]


def test_economic_scope_profile_modules_do_not_introduce_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f'{rel} must not contain forbidden token: {token}'


def test_economic_scope_profile_is_read_only_resolver() -> None:
    text = (ROOT / 'execution/economic_scope_profile.py').read_text(encoding='utf-8').lower()
    assert 'does not decide actions' in text
    assert 'does not compute economic policy' in text
