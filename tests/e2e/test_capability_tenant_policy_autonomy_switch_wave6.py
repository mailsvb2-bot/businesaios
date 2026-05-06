from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def test_full_autonomy_policy_restriction_fails_closed_to_notify_owner(tmp_path) -> None:
    harness = build_harness(
        tmp_path,
        scenario=[ScenarioStep(action_type='launch_campaign', output={'verified': True, 'goal_reached': True})],
        runtime_capabilities={'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
    )
    report = harness.run(
        make_request(
            goal='Scale ads safely',
            autonomy_tier='full_autonomy',
            meta={
                'runtime_capabilities': {'launch_campaign': {'enabled': True, 'healthy': True, 'health_score': 1.0}},
                'capability_policy': {
                    'supervised_only_capability_keys': ['ads_write'],
                }
            },
        )
    )
    step = report.steps[0]
    assert step.action == 'notify_owner'
    assert step.payload['capability_planning']['reason'] == 'policy_requires_supervised_autonomy'
    assert step.payload['operator_required'] is True
    assert report.final_feedback['capability_planning']['reason'] == 'policy_requires_supervised_autonomy'
