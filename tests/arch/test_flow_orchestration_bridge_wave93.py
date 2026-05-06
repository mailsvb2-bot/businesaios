from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_flow_execution_to_feedback_is_thin_reexport() -> None:
    content = (ROOT / "flow" / "execution_to_feedback_flow.py").read_text(encoding="utf-8")
    assert content.strip() == 'from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow\n\n__all__ = ["ExecutionToFeedbackFlow"]'


def test_orchestration_namespace_owns_canonical_execution_feedback_bridge() -> None:
    content = (ROOT / "orchestration" / "execution_feedback_bridge.py").read_text(encoding="utf-8")
    assert 'class ExecutionToFeedbackFlow:' in content
    assert 'return feedback_pipeline.run(execution_result)' in content


def test_flow_closed_loop_growth_is_thin_reexport() -> None:
    content = (ROOT / "flow" / "closed_loop_growth_flow.py").read_text(encoding="utf-8")
    assert content.strip() == 'from orchestration.closed_loop_growth_orchestrator import ClosedLoopGrowthFlow\n\n__all__ = ["ClosedLoopGrowthFlow"]'


def test_orchestration_namespace_owns_canonical_closed_loop_orchestrator() -> None:
    content = (ROOT / "orchestration" / "closed_loop_growth_orchestrator.py").read_text(encoding="utf-8")
    assert 'class ClosedLoopGrowthFlow:' in content
    assert "feedback = ExecutionToFeedbackFlow().run(execution_result, feedback_pipeline)" in content
    assert "strategy_feedback = FeedbackToStrategyFlow().run(feedback)" in content
