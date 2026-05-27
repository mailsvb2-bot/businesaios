from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_flow_decision_to_execution_is_thin_reexport() -> None:
    content = (ROOT / 'flow' / 'decision_to_execution_flow.py').read_text(encoding='utf-8')
    assert content.strip() == 'from execution.decision_execution_bridge import DecisionToExecutionFlow\n\n__all__ = ["DecisionToExecutionFlow"]'


def test_execution_namespace_owns_canonical_decision_execution_bridge() -> None:
    content = (ROOT / 'execution' / 'decision_execution_bridge.py').read_text(encoding='utf-8')
    assert 'class ExecutionRunPort(Protocol):' in content
    assert 'class DecisionToExecutionFlow:' in content
    assert "status='skipped'" in content
    assert 'return execution_pipeline.run(action)' in content


def test_flow_namespace_role_forbids_execution_ownership_drift() -> None:
    content = (ROOT / 'flow' / 'CANON_NAMESPACE_ROLE.md').read_text(encoding='utf-8')
    assert 'Forbidden:' in content
    assert 'generic execution primitives' in content
    assert 'action dispatch mechanics' in content
