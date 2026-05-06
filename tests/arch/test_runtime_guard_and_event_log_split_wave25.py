from pathlib import Path


def test_runtime_guard_delegates_reference_and_production_details() -> None:
    text = Path('runtime/guard.py').read_text(encoding='utf-8')
    assert 'from runtime.guard_reference import' in text
    assert 'from runtime.guard_production import' in text
    assert 'verify_and_lock_reference(' in text
    assert 'commit_reference_execution(' in text
    assert 'enforce_survival_gate(' in text


def test_event_log_delegates_scope_and_store_details() -> None:
    text = Path('core/events/log.py').read_text(encoding='utf-8')
    assert 'from core.events.log_scope import ensure_ctx_matches_event_log' in text
    assert 'from core.events.log_store import append_event_dict' in text
    assert 'ensure_ctx_matches_event_log(' in text
    assert 'append_event_dict(' in text
