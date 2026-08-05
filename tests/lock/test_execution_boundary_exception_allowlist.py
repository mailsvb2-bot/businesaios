from __future__ import annotations

import ast
from pathlib import Path


ROOTS = (Path('runtime/execution'), Path('execution'))
ALLOWED = {
    ('runtime/execution/executor_stages.py', 168): 'fail_closed_dispatch_reraise',
    ('runtime/execution/executor_observability.py', 53): 'best_effort_decision_trace',
    ('runtime/execution/executor_observability.py', 80): 'best_effort_action_audit',
    ('runtime/execution/executor_observability.py', 109): 'best_effort_inference_trace',
    ('runtime/execution/executor_observability.py', 140): 'best_effort_connector_observability',
    ('runtime/execution/executor_observability.py', 155): 'best_effort_effect_trace',
    ('runtime/execution/executor_observability.py', 177): 'best_effort_budget_burn_observability',
    ('runtime/execution/executor_autonomy_gate.py', 88): 'best_effort_denial_event_before_runtime_error',
    ('runtime/execution/executor_queue_runtime.py', 33): 'best_effort_queue_tick_event',
    ('runtime/execution/executor_trace_runtime.py', 59): 'best_effort_runtime_trace',
    ('runtime/execution/executor_trace_runtime.py', 136): 'fail_closed_executor_exception_reraise',
    ('runtime/execution/executor_trace_runtime.py', 212): 'fail_closed_core_flow_reraise',
    ('runtime/execution/executor_trace_runtime.py', 229): 'best_effort_secondary_checkpoint',
    ('runtime/execution/world_model_pin_runtime.py', 42): 'best_effort_pin_check_event',
    ('execution/evidence_persistence_reliability.py', 127): 'best_effort_secondary_failure_marker',
    ('execution/evidence_persistence_reliability.py', 245): 'fail_closed_persistence_reraise',
    ('execution/closed_loop_orchestrator.py', 602): 'fail_closed_cycle_audit_reraise',
    ('execution/inference_dispatch_orchestrator.py', 156): 'provider_breaker_record_then_reraise',
    ('execution/inference_dispatch_orchestrator.py', 188): 'bounded_provider_failover',
    ('execution/market_intelligence_loop.py', 235): 'bounded_provider_retry_and_terminal_failure',
}


def _broad_handlers() -> dict[tuple[str, int], ast.ExceptHandler]:
    handlers: dict[tuple[str, int], ast.ExceptHandler] = {}
    for root in ROOTS:
        for path in root.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                broad = node.type is None or (
                    isinstance(node.type, ast.Name) and node.type.id in {'Exception', 'BaseException'}
                )
                if broad:
                    handlers[(path.as_posix(), node.lineno)] = node
    return handlers


def test_execution_zone_broad_handlers_match_reviewed_boundary_allowlist() -> None:
    handlers = _broad_handlers()

    assert set(handlers) == set(ALLOWED)
    assert all(classification.strip() for classification in ALLOWED.values())


def test_fail_closed_boundaries_reraise() -> None:
    handlers = _broad_handlers()
    fail_closed = {
        key for key, classification in ALLOWED.items()
        if 'fail_closed' in classification or 'reraise' in classification
    }

    for key in fail_closed:
        assert any(isinstance(node, ast.Raise) for node in ast.walk(handlers[key])), (key, ALLOWED[key])
