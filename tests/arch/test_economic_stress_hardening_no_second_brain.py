from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    'execution/economic_bundle_quarantine_store.py',
    'execution/economic_schema_validation.py',
    'execution/economic_segment_validation.py',
    'execution/economic_semantic_validation.py',
    'execution/economic_scope_lineage.py',
    'execution/economic_replay_epoch_guard.py',
    'execution/economic_split_brain_guard.py',
    'execution/economic_backend_authority.py',
    'execution/economic_policy_fingerprint.py',
    'execution/economic_anchor_preservation.py',
]

FORBIDDEN = [
    'DecisionCore(',
    'RuntimeDecisionCore',
    'def decide(',
    'def issue(',
    'from core.ai.decision_core import DecisionCore',
    'from core.decision_core import DecisionCore',
]


def test_economic_stress_hardening_modules_do_not_create_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        for token in FORBIDDEN:
            assert token not in text, f'{rel} contains forbidden token: {token}'
