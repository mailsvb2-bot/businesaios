from pathlib import Path


def test_closed_loop_orchestrator_uses_economic_state_owner() -> None:
    source = Path("execution/closed_loop_orchestrator.py").read_text(encoding="utf-8")
    assert "from execution.closed_loop_economic_state import (" in source
    assert "def _stable_reliability_trace" in source
    assert "return _stable_reliability_trace_owner(" in source
    assert "return _economic_event_id_owner(" in source
    assert "return _apply_economic_history_to_state_owner(" in source


def test_business_operating_memory_uses_store_support_owner() -> None:
    source = Path("execution/business_operating_memory.py").read_text(encoding="utf-8")
    assert "from execution.business_memory_store_support import (" in source
    assert "return _migrate_business_memory_payload_owner(payload, policy=policy)" in source
    assert "return _run_record_from_row_owner(row, policy=policy)" in source
    assert "return _signal_record_from_row_owner(row, policy=policy)" in source
