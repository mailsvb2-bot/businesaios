from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    ROOT / 'runtime' / 'scheduler_parts' / 'decision_request.py',
    ROOT / 'runtime' / 'self_driving_scheduler.py',
    ROOT / 'runtime' / 'scheduler_parts' / 'deploy_flow.py',
    ROOT / 'runtime' / 'scheduler_parts' / 'monitoring.py',
)


def test_runtime_scheduler_paths_use_decision_gateway_helper() -> None:
    violations: list[str] = []
    for path in TARGETS:
        text = path.read_text(encoding='utf-8')
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith('decision_request.py'):
            if 'execute_runtime_decision' not in text:
                violations.append(f'{rel}:missing_decision_gateway_execution_helper')
            if 'executor.execute(' in text:
                violations.append(f'{rel}:raw_executor_execute_present')
            if 'issue_runtime_decision(' in text:
                violations.append(f'{rel}:raw_issue_runtime_decision_present')
            continue
        if 'request_scheduler_decision_execution' not in text:
            violations.append(f'{rel}:missing_request_helper')
        if '.issue(ws)' in text or '.issue(state)' in text or 'issue_runtime_decision' in text:
            violations.append(f'{rel}:raw_issue_call_present')
    assert violations == [], violations
