from __future__ import annotations

from pathlib import Path


def test_remaining_p1_p2_analytics_layers_stay_out_of_decision_and_execution():
    root = Path(__file__).resolve().parents[2]
    targets = [
        root / 'application' / 'analytics' / 'distributed_analytics_materializer_lock.py',
        root / 'application' / 'analytics' / 'persistent_distributed_analytics_materializer.py',
        root / 'application' / 'analytics' / 'analytics_signing_key_resolver.py',
        root / 'application' / 'analytics' / 'analytics_manifest_chain_store.py',
        root / 'application' / 'analytics' / 'analytics_signed_export_chain_service.py',
        root / 'application' / 'analytics' / 'analytics_delivery_service.py',
        root / 'application' / 'analytics' / 'fleet_analytics_coordinator.py',
        root / 'application' / 'analytics' / 'fleet_analytics_scheduler.py',
        root / 'app' / 'web' / 'components' / 'analytics_dashboard_card.py',
        root / 'app' / 'web' / 'components' / 'analytics_explainability_card.py',
        root / 'app' / 'web' / 'components' / 'analytics_rollup_card.py',
        root / 'app' / 'web' / 'pages' / 'analytics.py',
    ]
    forbidden = ['DecisionCore(', '.optimize(', 'execute_action(', 'dispatch_action(', 'from execution', 'import execution', 'from runtime.execution', 'import runtime.execution', 'goal_decomposition', 'autonomy_policy']
    for path in targets:
        text = path.read_text(encoding='utf-8')
        for marker in forbidden:
            assert marker not in text, f'{path} must remain analytics-only; found {marker}'
