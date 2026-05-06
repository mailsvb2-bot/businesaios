from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def test_combined_tenant_and_business_overrides_fail_closed_and_surface_policy_scope(tmp_path) -> None:
    harness = build_harness(
        tmp_path,
        scenario=[ScenarioStep(action_type='launch_campaign', output={'verified': True, 'goal_reached': True})],
        runtime_capabilities={'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
    )
    report = harness.run(
        make_request(
            goal='Scale paid growth carefully',
            autonomy_tier='full_autonomy',
            meta={
                'runtime_capabilities': {'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
                'capability_policy': {
                    'supervised_only_capability_keys': ['ads_write'],
                    'business_overrides': {
                        'biz-1': {'max_autonomy_tier_by_capability_key': {'ads_write': 'bounded_autonomy'}},
                    },
                },
            },
        )
    )

    step = report.steps[0]
    assert step.action == 'notify_owner'
    assert step.payload['capability_planning']['reason'] == 'policy_requires_supervised_autonomy'
    assert step.payload['capability_planning']['capability']['policy_verdict']['policy_scope'] == 'tenant'
    assert report.final_feedback['capability_view']['policy_verdict']['allowed'] is False
    assert report.final_feedback['operator_required'] is True


def test_combined_stale_and_degraded_capability_recovery_chain_preserves_capability_view(tmp_path) -> None:
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
            goal='Scale paid growth',
            autonomy_tier='bounded_autonomy',
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
                    'business_overrides': {
                        'biz-1': {'max_autonomy_tier_by_capability_key': {'ads_write': 'bounded_autonomy'}},
                    },
                },
            },
        )
    )

    step = report.steps[0]
    assert step.action == 'notify_owner'
    assert step.payload['capability_planning']['fallback_used'] is True
    capability_view = report.final_feedback['capability_view']
    assert capability_view['diagnostics']['status'] == 'fallback'
    assert capability_view['diagnostics']['operator_action'] in {'operator_handoff', 'review_and_handoff'}
    assert capability_view['execution_verdict']['operator_required'] is True
