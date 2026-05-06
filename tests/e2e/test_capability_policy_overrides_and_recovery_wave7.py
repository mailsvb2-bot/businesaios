from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def test_business_override_restricts_full_autonomy_and_fails_closed(tmp_path) -> None:
    harness = build_harness(
        tmp_path,
        scenario=[ScenarioStep(action_type='launch_campaign', output={'verified': True, 'goal_reached': True})],
        runtime_capabilities={'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
    )
    report = harness.run(
        make_request(
            goal='Scale paid growth',
            autonomy_tier='full_autonomy',
            meta={
                'runtime_capabilities': {'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
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
    assert step.payload['capability_planning']['reason'] == 'policy_autonomy_tier_exceeded'
    assert step.payload['capability_planning']['capability']['policy_verdict']['policy_scope'] == 'business:biz-1'


def test_stale_capability_with_operator_handoff_remains_safe_during_recovery_semantics(tmp_path) -> None:
    harness = build_harness(
        tmp_path,
        scenario=[ScenarioStep(action_type='launch_campaign', output={'verified': False, 'goal_reached': False})],
        runtime_capabilities={'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 0.8, 'staleness_state': 'stale', 'evidence_state': 'sufficient'}},
    )
    report = harness.run(
        make_request(
            goal='Scale paid growth',
            autonomy_tier='bounded_autonomy',
            meta={
                'runtime_capabilities': {'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 0.8, 'staleness_state': 'stale', 'evidence_state': 'sufficient'}},
            },
        )
    )
    step = report.steps[0]
    assert step.action == 'notify_owner'
    assert step.payload['capability_planning']['fallback_used'] is True
    assert step.payload['capability_planning']['capability']['diagnostics']['status'] == 'fallback'
    assert report.final_feedback['operator_required'] is True
