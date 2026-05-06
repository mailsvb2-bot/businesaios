from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path('.')
MESSAGING_OBSERVABILITY_ROOTS = (
    'interfaces/web/debug/messaging_policy_snapshot/',
    'interfaces/web/debug/messaging_policy_trace_search/',
    'interfaces/web/debug/messaging_policy_dashboard/',
    'interfaces/web/debug/messaging_policy_alerts/',
    'interfaces/web/debug/messaging_policy_observability_nav/',
    'interfaces/web/settings/alert_subscriptions/',
    'interfaces/web/settings/alert_subscriptions_integration/',
    'interfaces/web/settings/messaging_preferences/',
    'interfaces/web/settings/messaging_preferences_integration/',
    'runtime/messaging_policy_alerts/',
    'runtime/messaging_policy_alert_subscriptions/',
    'runtime/messaging_policy_alert_dedup/',
    'runtime/messaging_policy_alert_dedup_persistent/',
    'runtime/messaging_policy_dashboard/',
    'runtime/messaging_policy_trace/',
)
FORBIDDEN_IMPORT_MODULES = {
    'core.decision',
    'core.decision_core',
    'application.decisioning',
    'runtime.execution.decision_execution_service',
    'runtime.execution.executor_entrypoint_bundle',
    'execution.autonomy_loop',
    'execution.closed_loop_orchestrator',
    'core.ai_ceo',
    'core.world_model',
}
FORBIDDEN_TEXT_PATTERNS = {
    'DecisionCore(': 'observability contour must not construct DecisionCore',
    'decide(': 'observability contour must not issue decisions',
    'compose_sync(': 'observability contour must not generate business text',
    'optimize(': 'observability contour must not optimize business strategy',
    'select_strategy': 'observability contour must not choose strategy',
    'world_model_score': 'observability contour must not score world model state',
}
ALLOWED_TEXT_EXCEPTIONS = {
    'runtime/messaging_policy_alert_subscriptions/notification_text_parts.py',
    'runtime/messaging_policy_alert_subscriptions/notification_text_builder.py',
}

def _py_files():
    return [p for p in ROOT.rglob('*.py') if '.venv/' not in p.as_posix()]

def _is_target(rel: str) -> bool:
    return any(rel.startswith(root) for root in MESSAGING_OBSERVABILITY_ROOTS)

def test_repo_wide_messaging_observability_contour_does_not_import_decision_layers() -> None:
    offenders=[]
    for path in _py_files():
        rel=path.as_posix()
        if not _is_target(rel) or rel.startswith('tests/'):
            continue
        tree=ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        found=False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in FORBIDDEN_IMPORT_MODULES:
                found=True
            elif isinstance(node, ast.Import):
                names={alias.name for alias in node.names}
                if names & FORBIDDEN_IMPORT_MODULES:
                    found=True
            if found:
                offenders.append(rel)
                break
    assert not offenders, offenders

def test_repo_wide_messaging_observability_contour_does_not_drift_into_hidden_decision_text_patterns() -> None:
    offenders=[]
    for path in _py_files():
        rel=path.as_posix()
        if not _is_target(rel) or rel.startswith('tests/') or rel in ALLOWED_TEXT_EXCEPTIONS:
            continue
        text=path.read_text(encoding='utf-8')
        for pattern, reason in FORBIDDEN_TEXT_PATTERNS.items():
            if pattern in text:
                offenders.append(f'{rel}: {reason}')
    assert not offenders, offenders
