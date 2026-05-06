from pathlib import Path


def test_outcome_persistence_owner_exists() -> None:
    text = Path('runtime/execution/outcome_persistence_lock.py').read_text(encoding='utf-8')
    assert 'CANON_RUNTIME_OUTCOME_PERSISTENCE_LOCK_OWNER = True' in text
    assert 'def persist_verified_outcome(' in text
    assert 'def finalize_recovered_outcome(' in text


def test_execution_contract_and_recovery_use_outcome_persistence_owner() -> None:
    contract = Path('runtime/execution/execution_contract_lock.py').read_text(encoding='utf-8')
    recovery = Path('runtime/executor_recovery_flow.py').read_text(encoding='utf-8')
    assert 'persist_verified_outcome(' in contract
    assert 'mark_delivered(' not in contract
    assert 'emit_decision_executed(' not in contract
    assert 'finalize_recovered_outcome(' in recovery
    assert 'mark_delivered(' not in recovery
