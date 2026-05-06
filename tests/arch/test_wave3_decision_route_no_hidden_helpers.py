from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_targeted_runtime_and_api_surfaces_do_not_call_raw_decision_methods() -> None:
    targets = {
        'runtime/decision_gateway.py': ('.decide(', '.optimize('),
        'runtime/scheduler_parts/decision_request.py': ('.issue(', '.decide(', '.optimize(', 'executor.execute('),
        'application/headless/decision_gateway.py': ('.decide(', '.optimize('),
        'interfaces/api/runtime_api_bundle.py': ('.issue(', '.decide(', '.optimize(', 'executor.execute('),
        'interfaces/api/execute_action_stack_bundle.py': ('.issue(', '.decide(', '.optimize(', 'executor.execute('),
        'runtime/application/_ports_impl.py': ('.issue(', '.decide(', '.optimize(', 'executor.execute('),
    }
    for relative_path, forbidden_tokens in targets.items():
        text = _text(relative_path)
        for token in forbidden_tokens:
            assert token not in text, f'{relative_path} must not contain raw helper token {token}'


def test_targeted_scheduler_and_headless_surfaces_route_through_single_owners() -> None:
    scheduler = _text('runtime/scheduler_parts/decision_request.py')
    gateway = _text('runtime/decision_gateway.py')
    headless = _text('application/headless/decision_gateway.py')
    app_ports = _text('runtime/application/_ports_impl.py')

    assert 'execute_runtime_decision(' in scheduler
    assert 'issue_locked_decision(' in gateway
    assert 'lock_execution_envelope(' in gateway
    assert 'issue_locked_decision(' in headless
    assert 'execute_locked_application_action(' in app_ports


def test_runtime_entrypoint_docs_do_not_point_to_optimize_as_owner() -> None:
    text = _text('runtime/entrypoints/telegram_longpoll.py')
    assert 'DecisionCore.issue(WorldState) is the only decision source.' in text
    assert 'DecisionCore.optimize(WorldState) is the only decision source.' not in text
