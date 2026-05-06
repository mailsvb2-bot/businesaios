from pathlib import Path


def test_business_memory_projection_owner_exists() -> None:
    text = Path('execution/business_memory_projection.py').read_text(encoding='utf-8')
    assert 'CANON_BUSINESS_MEMORY_PROJECTION_OWNER = True' in text
    owner_text = Path('execution/business_operating_memory.py').read_text(encoding='utf-8')
    assert '_project_business_memory_contract_bundle_owner' in owner_text
    assert '_project_business_memory_meta_payloads_owner' in owner_text


def test_approval_gate_fingerprint_owner_exists() -> None:
    text = Path('execution/approval_gate_fingerprint.py').read_text(encoding='utf-8')
    assert 'CANON_APPROVAL_GATE_FINGERPRINT_OWNER = True' in text
    gate_text = Path('execution/approval_execution_gate.py').read_text(encoding='utf-8')
    assert 'from execution.approval_gate_fingerprint import build_execution_subject_fingerprint' in gate_text


def test_closed_loop_support_owner_exists() -> None:
    text = Path('execution/closed_loop_support.py').read_text(encoding='utf-8')
    assert 'def build_recovery_summary' in text
    orchestrator_text = Path('execution/closed_loop_orchestrator.py').read_text(encoding='utf-8')
    assert '_build_recovery_summary_owner' in orchestrator_text
    assert '_normalize_approval_context_owner' in orchestrator_text
    assert '_build_approval_handoff_owner' in orchestrator_text
