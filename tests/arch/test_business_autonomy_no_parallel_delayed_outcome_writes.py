from __future__ import annotations

from pathlib import Path


def test_business_autonomy_no_parallel_delayed_outcome_writes() -> None:
    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    allowed = {
        'application/business_autonomy/delayed_outcome_bridge.py',
        'tests/unit/application/test_business_autonomy_delayed_outcome_sweeper.py',
        'tests/unit/application/test_business_autonomy_delayed_outcome_admin_plane.py',
        'tests/unit/application/test_business_autonomy_delayed_outcome_recovery_actions.py',
        'tests/unit/application/test_business_autonomy_delayed_outcome_crash_resume.py',
        'tests/interfaces/test_business_autonomy_route_handlers_delayed_outcome_actions.py',
        'tests/arch/test_business_autonomy_no_parallel_delayed_outcome_writes.py',
    }
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        if rel in allowed or rel.startswith('.venv/'):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if 'delayed_outcomes.jsonl' in text or 'delayed_outcome_quarantine.jsonl' in text:
            offenders.append(rel)
    assert not offenders, f'parallel delayed-outcome paths found: {offenders}'
