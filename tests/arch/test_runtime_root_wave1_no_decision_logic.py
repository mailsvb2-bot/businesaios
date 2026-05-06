from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_root_surfaces_do_not_import_or_issue_decisions() -> None:
    files = [
        'runtime/runtime_orchestrator.py',
        'runtime/recovery.py',
        'runtime/bootstrap.py',
        'runtime/runtime_boot.py',
    ]
    for relative in files:
        text = _read(relative)
        assert '.issue(' not in text, relative
        assert 'DecisionCore' not in text, relative
        assert 'from runtime.executor import RuntimeExecutor' not in text or relative.endswith('recovery.py')


def test_runtime_recovery_is_fail_closed_and_has_no_resume_fallback_aliases() -> None:
    text = _read('runtime/recovery.py')
    assert 'CANON_RUNTIME_RECOVERY_FAIL_CLOSED = True' in text
    assert 'unknown_recovery_action_' in text
    assert 'runtime_recovery_fallback' not in text
    assert 'fallback": "mark_delivered"' not in text
