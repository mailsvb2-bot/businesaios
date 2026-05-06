from __future__ import annotations

from pathlib import Path


def test_analytics_api_and_runtime_wiring_stay_out_of_decision_and_execution():
    root = Path(__file__).resolve().parents[2]
    targets = [
        root / 'entrypoints' / 'api' / 'analytics_models.py',
        root / 'entrypoints' / 'api' / 'analytics_route_handlers.py',
        root / 'entrypoints' / 'api' / 'analytics_ops_route_handlers.py',
        root / 'adapters' / 'api' / 'fastapi' / 'analytics_routes.py',
        root / 'adapters' / 'api' / 'fastapi' / 'analytics_ops_routes.py',
        root / 'application' / 'analytics' / 'fleet_queue_job_bridge.py',
        root / 'runtime' / '_internal' / 'effects_domains' / 'analytics_delivery_executor.py',
    ]
    forbidden = [
        'DecisionCore(', '.optimize(', 'execute_action(', 'dispatch_action(',
        'from execution', 'import execution', 'from runtime.execution', 'import runtime.execution',
        'goal_decomposition', 'autonomy_policy',
    ]
    for path in targets:
        text = path.read_text(encoding='utf-8')
        for marker in forbidden:
            assert marker not in text, f'{path} must remain analytics-only; found {marker}'
