from pathlib import Path


def test_evidence_persistence_support_owners_exist() -> None:
    feedback = Path('execution/evidence_persistence_feedback.py').read_text(encoding='utf-8')
    reliability = Path('execution/evidence_persistence_reliability.py').read_text(encoding='utf-8')
    persistence = Path('execution/evidence_persistence.py').read_text(encoding='utf-8')
    assert 'CANON_EVIDENCE_PERSISTENCE_FEEDBACK = True' in feedback
    assert 'CANON_EVIDENCE_PERSISTENCE_RELIABILITY = True' in reliability
    assert 'from execution.evidence_persistence_feedback import (' in persistence
    assert 'from execution.evidence_persistence_reliability import EvidencePersistenceReliabilitySupport' in persistence
    assert 'self._reliability = EvidencePersistenceReliabilitySupport(' in persistence


def test_approval_gate_support_owner_exists() -> None:
    support = Path('execution/approval_gate_support.py').read_text(encoding='utf-8')
    gate = Path('execution/approval_execution_gate.py').read_text(encoding='utf-8')
    assert 'CANON_APPROVAL_GATE_SUPPORT = True' in support
    assert 'from execution.approval_gate_support import (' in gate
    assert 'build_handoff as _build_handoff' in gate
    assert 'new_approval_id as _new_approval_id' in gate
