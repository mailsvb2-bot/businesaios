from __future__ import annotations

from pathlib import Path


def test_analytics_layers_stay_out_of_decision_and_execution():
    root = Path(__file__).resolve().parents[2]
    targets = [
        root / 'core' / 'analytics' / 'business_scorecard.py',
        root / 'core' / 'analytics' / 'analytics_dashboard.py',
        root / 'core' / 'analytics' / 'analytics_explainability_trace.py',
        root / 'core' / 'analytics' / 'analytics_rollup.py',
        root / 'application' / 'analytics' / 'dashboard_service.py',
        root / 'application' / 'analytics' / 'analytics_materializer.py',
        root / 'app' / 'web' / 'pages' / 'analytics.py',
    ]
    forbidden = ['DecisionCore(', '.optimize(', 'execute_action(', 'dispatch_action(', 'from execution', 'import execution', 'from runtime.execution', 'import runtime.execution']
    for path in targets:
        text = path.read_text(encoding='utf-8')
        for marker in forbidden:
            assert marker not in text, f'{path} must remain analytics-only; found {marker}'
