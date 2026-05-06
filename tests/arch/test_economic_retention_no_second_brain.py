from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    'execution/economic_retention_policy.py',
    'execution/economic_multi_backend_reconciliation.py',
]
FORBIDDEN_TOKENS = [
    'class DecisionCore',
    'RuntimeDecisionCore',
    'def decide(',
    'def issue(',
    'from core.ai.decision_core import DecisionCore',
    'from core.decision_core import DecisionCore',
]


def test_economic_retention_wave_does_not_introduce_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f'{rel} must not contain forbidden token: {token}'
