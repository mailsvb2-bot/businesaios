from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_flow_signal_to_opportunity_is_thin_reexport() -> None:
    content = (ROOT / 'flow' / 'signal_to_opportunity_flow.py').read_text(encoding='utf-8')
    assert content.strip() == 'from orchestration.signal_opportunity_bridge import SignalToOpportunityFlow\n\n__all__ = ["SignalToOpportunityFlow"]'


def test_flow_opportunity_to_decision_is_thin_reexport() -> None:
    content = (ROOT / 'flow' / 'opportunity_to_decision_flow.py').read_text(encoding='utf-8')
    assert content.strip() == 'from orchestration.opportunity_decision_bridge import OpportunityToDecisionFlow\n\n__all__ = ["OpportunityToDecisionFlow"]'


def test_flow_feedback_to_strategy_is_thin_reexport() -> None:
    content = (ROOT / 'flow' / 'feedback_to_strategy_flow.py').read_text(encoding='utf-8')
    assert content.strip() == 'from orchestration.strategy_feedback_bridge import FeedbackToStrategyFlow\n\n__all__ = ["FeedbackToStrategyFlow"]'


def test_orchestration_namespace_owns_remaining_flow_handoffs() -> None:
    signal_content = (ROOT / 'orchestration' / 'signal_opportunity_bridge.py').read_text(encoding='utf-8')
    assert 'class SignalToOpportunityFlow:' in signal_content
    assert 'return opportunity_pipeline.run(signals)' in signal_content

    decision_content = (ROOT / 'orchestration' / 'opportunity_decision_bridge.py').read_text(encoding='utf-8')
    assert 'class OpportunityToDecisionFlow:' in decision_content
    assert 'return decision_pipeline.run(candidates, constraints)' in decision_content

    feedback_content = (ROOT / 'orchestration' / 'strategy_feedback_bridge.py').read_text(encoding='utf-8')
    assert 'class FeedbackToStrategyFlow:' in feedback_content
    assert "return {'strategy_feedback': dict(feedback)}" in feedback_content


def test_closed_loop_orchestrator_uses_orchestration_owned_handoffs() -> None:
    content = (ROOT / 'orchestration' / 'closed_loop_growth_orchestrator.py').read_text(encoding='utf-8')
    assert 'from orchestration.signal_opportunity_bridge import SignalToOpportunityFlow' in content
    assert 'from orchestration.opportunity_decision_bridge import OpportunityToDecisionFlow' in content
    assert 'from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow' in content
    assert 'from orchestration.strategy_feedback_bridge import FeedbackToStrategyFlow' in content
    assert 'from flow.signal_to_opportunity_flow' not in content
    assert 'from flow.opportunity_to_decision_flow' not in content
    assert 'from flow.execution_to_feedback_flow' not in content
    assert 'from flow.feedback_to_strategy_flow' not in content


def test_feedback_boot_uses_canonical_orchestration_handoff() -> None:
    content = (ROOT / 'boot' / 'feedback_boot.py').read_text(encoding='utf-8')
    assert 'from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow' in content
    assert 'from flow.execution_to_feedback_flow import ExecutionToFeedbackFlow' not in content
