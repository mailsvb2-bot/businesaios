from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_headless_execution_gateway_is_single_owner_surface() -> None:
    text = _text('application/headless/execution_gateway.py')
    assert 'CANON_HEADLESS_EXECUTION_GATEWAY_SINGLE_PATH = True' in text
    assert 'CANON_HEADLESS_EXECUTION_GATEWAY_EXECUTION_OWNER = True' in text
    assert 'def execute_headless_envelope(' in text
    assert 'def validate_headless_executor(' in text


def test_autonomy_execution_step_uses_headless_execution_gateway() -> None:
    text = _text('application/autonomy/autonomy_execution_step.py')
    assert 'CANON_AUTONOMY_EXECUTION_STEP_GATEWAY_EXECUTION_OWNER = True' in text
    assert 'execute_headless_envelope(' in text
    assert '._executor.execute(' not in text


def test_headless_contract_uses_shared_executor_validation() -> None:
    text = _text('execution/headless_contract.py')
    assert 'validate_headless_executor(executor)' in text
    assert "_require_method(executor, 'execute', 'executor')" not in text
