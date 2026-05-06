from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def test_combined_policy_override_chain_preserves_final_capability_surface(tmp_path) -> None:
    harness = build_harness(
        tmp_path,
        scenario=[ScenarioStep(action_type='launch_campaign', output={'verified': False, 'goal_reached': False})],
        runtime_capabilities={
            'launch_campaign': {
                'enabled': True,
                'healthy': False,
                'degraded': True,
                'health_score': 0.22,
                'staleness_state': 'stale',
                'evidence_state': 'insufficient',
            }
        },
    )

    report = harness.run(
        make_request(
            goal='Scale paid growth carefully',
            autonomy_tier='full_autonomy',
            meta={
                'runtime_capabilities': {
                    'launch_campaign': {
                        'enabled': True,
                        'healthy': False,
                        'degraded': True,
                        'health_score': 0.22,
                        'staleness_state': 'stale',
                        'evidence_state': 'insufficient',
                    }
                },
                'capability_policy': {
                    'supervised_only_capability_keys': ['ads_write'],
                    'business_overrides': {
                        'biz-1': {'max_autonomy_tier_by_capability_key': {'ads_write': 'bounded_autonomy'}},
                    },
                },
            },
        )
    )

    capability_view = report.final_feedback['capability_view']
    assert report.steps[0].action == 'notify_owner'
    assert capability_view['policy_verdict']['allowed'] is False
    assert capability_view['policy_verdict']['reason'] == 'policy_requires_supervised_autonomy'
    assert capability_view['execution_verdict']['operator_required'] is True
    assert capability_view['execution_verdict']['blocked_by_policy'] is True
    assert capability_view['diagnostics']['status'] in {'blocked', 'fallback'}
