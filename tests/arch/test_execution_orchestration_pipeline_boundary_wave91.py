from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_orchestration_execution_pipeline_is_thin_reexport() -> None:
    content = (ROOT / "orchestration" / "execution_pipeline.py").read_text(encoding="utf-8")
    assert content.strip() == 'from execution.execution_pipeline import ExecutionPipeline\n\n__all__ = ["ExecutionPipeline"]'


def test_execution_namespace_owns_canonical_execution_pipeline() -> None:
    content = (ROOT / "execution" / "execution_pipeline.py").read_text(encoding="utf-8")
    assert 'class ActionDispatchPort(Protocol):' in content
    assert 'class ExecutionPipeline:' in content
    assert 'return self._dispatcher.dispatch(action)' in content


def test_orchestration_namespace_role_forbids_execution_ownership_drift() -> None:
    content = (ROOT / "orchestration" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    assert 'Forbidden:' in content
    assert 'generic execution primitives' in content
    assert 'action dispatch mechanics' in content
