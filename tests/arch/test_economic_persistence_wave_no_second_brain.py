from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    'execution/economic_memory_store.py',
    'execution/replay_safe_roi_history.py',
]
FORBIDDEN = [
    'class DecisionCore',
    'RuntimeDecisionCore',
    'def decide(',
    'def issue(',
    'from core.ai.decision_core import DecisionCore',
    'from core.decision_core import DecisionCore',
]


def test_persistence_wave_modules_do_not_introduce_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        for token in FORBIDDEN:
            assert token not in text, f'{rel} must not contain forbidden token: {token}'
