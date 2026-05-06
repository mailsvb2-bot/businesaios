from pathlib import Path


def test_execution_contract_owner_exists() -> None:
    path = Path('runtime/execution/execution_contract_lock.py')
    text = path.read_text(encoding='utf-8')
    assert 'CANON_RUNTIME_EXECUTION_CONTRACT_LOCK_OWNER = True' in text
    assert 'def verify_execution_contract(' in text
    assert 'def commit_verified_execution(' in text


def test_executor_stages_use_contract_owner_instead_of_local_commit_path() -> None:
    text = Path('runtime/execution/executor_stages.py').read_text(encoding='utf-8')
    assert 'verify_execution_contract(executor=executor, env=env, output=out)' in text
    assert 'commit_verified_execution(executor=executor, env=env, output=out, verification_result=verification_result)' in text
    assert 'mark_delivered(' not in text
    assert 'emit_decision_executed(' not in text
