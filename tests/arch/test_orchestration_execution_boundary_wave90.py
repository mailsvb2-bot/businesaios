from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_orchestration_idempotency_uses_execution_primitives() -> None:
    content = (ROOT / 'orchestration' / 'idempotency.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import SetIdempotencyGate' in content
    assert 'self._gate = SetIdempotencyGate(self.seen_keys)' in content


def test_orchestration_retry_policy_uses_execution_primitives() -> None:
    content = (ROOT / 'orchestration' / 'retry_policy.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import RetryableStatusSet' in content
    assert 'temporary_failure' in content
    assert 'rate_limited' in content
