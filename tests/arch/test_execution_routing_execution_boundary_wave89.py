from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_execution_and_routing_execution_roles_are_documented() -> None:
    execution_role = ROOT / 'execution' / 'CANON_NAMESPACE_ROLE.md'
    routing_role = ROOT / 'routing_execution' / 'CANON_NAMESPACE_ROLE.md'
    assert execution_role.exists()
    assert routing_role.exists()


def test_routing_execution_idempotency_reuses_execution_primitives() -> None:
    source = (ROOT / 'routing_execution' / 'lead_delivery_idempotency.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import SetIdempotencyGate' in source
    assert 'set()' not in source


def test_routing_execution_retry_reuses_execution_primitives() -> None:
    source = (ROOT / 'routing_execution' / 'lead_delivery_retry.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import StatusRetryPolicy' in source
    assert 'MAX_RETRY_ATTEMPTS' in source


def test_execution_action_idempotency_reuses_execution_primitives() -> None:
    source = (ROOT / 'execution' / 'action_idempotency.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import SetIdempotencyGate' in source
