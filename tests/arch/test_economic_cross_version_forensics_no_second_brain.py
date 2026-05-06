from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    'execution/economic_schema_migration_matrix.py',
    'compliance/economic_forensics_contract.py',
    'compliance/economic_forensics_store.py',
    'compliance/economic_forensics_service.py',
]
FORBIDDEN = [
    'DecisionCore(',
    'RuntimeDecisionCore',
    'def decide(',
    'def issue(',
    'from core.ai.decision_core import DecisionCore',
    'from core.decision_core import DecisionCore',
]


def test_cross_version_and_forensics_modules_do_not_create_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        for token in FORBIDDEN:
            assert token not in text, f'{rel} contains forbidden token: {token}'
