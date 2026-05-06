from pathlib import Path


def test_evidence_persistence_delegates_world_state_projection_to_owner() -> None:
    text = Path('execution/evidence_persistence.py').read_text(encoding='utf-8')
    assert 'from execution.evidence_feedback_state import apply_feedback_to_world_state as _apply_feedback_world_state' in text
    assert 'project_business_memory_evidence' not in text
    assert 'project_business_memory_governance_summary' not in text
    assert 'return _apply_feedback_world_state(' in text


def test_evidence_feedback_state_owns_business_memory_projection() -> None:
    text = Path('execution/evidence_feedback_state.py').read_text(encoding='utf-8')
    assert 'project_business_memory_evidence' in text
    assert 'project_business_memory_governance_summary' in text
    assert 'def apply_feedback_to_world_state(' in text
