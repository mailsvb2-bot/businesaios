from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]
def test_owner_path_replay_and_resume_keep_one_canonical_trace(tmp_path) -> None:
    first = build_harness(
        tmp_path / 'first',
        scenario=[ScenarioStep(action_type='route_lead', output={'verified': True, 'goal_reached': True, 'terminal': True, 'external_refs': ['crm:lead:owner-path']})],
    )
    original = first.run(make_request(goal='Resume owner path', max_steps=1))
    record = first.read_single_ledger_record()
    second = build_harness(
        tmp_path / 'second',
        scenario=[ScenarioStep(action_type='route_lead', output={'verified': True, 'goal_reached': True, 'terminal': True, 'external_refs': ['crm:lead:owner-path']})],
    )
    second.run(make_request(goal='Resume owner path', max_steps=1))
    replayed = second.replay.replay(record)
    owner_path = dict(replayed.final_feedback['owner_path'])
    assert original.final_feedback['owner_path']['observation_count'] == 1
    assert owner_path['observation_count'] >= 2
    assert owner_path['resumed_from_previous_run'] is True
    assert owner_path['stage_observation_counts']['verification'] >= 1
    assert owner_path['last_decision_id'] and owner_path['last_correlation_id']
def test_owner_path_handles_failure_degradation_recovery_and_stays_single(tmp_path) -> None:
    shared = tmp_path / 'shared'
    failed = build_harness(shared, scenario=[ScenarioStep(action_type='notify_owner', output={'verified': False, 'goal_reached': False})])
    failed_report = failed.run(make_request(goal='Recover verified listing publication', max_steps=1))
    assert failed_report.completed is False
    degraded = build_harness(
        shared,
        scenario=[ScenarioStep(action_type='notify_owner', output={'verified': False, 'goal_reached': False})],
        runtime_capabilities={'create_listing': {'enabled': True, 'healthy': False, 'health_score': 0.10}},
    )
    degraded_report = degraded.run(make_request(goal='Recover verified listing publication', max_steps=1, meta={'runtime_capabilities': {'create_listing': {'enabled': True, 'healthy': False, 'health_score': 0.10}}}))
    assert degraded_report.completed is False
    recovered = build_harness(
        shared,
        scenario=[ScenarioStep(action_type='create_listing', output={'verified': True, 'goal_reached': True, 'terminal': True, 'external_refs': ['listing:ok']})],
        runtime_capabilities={'create_listing': {'enabled': True, 'healthy': True, 'health_score': 0.98}},
    )
    for _ in range(4):
        recovered.capability_health_service.update_after_step(tenant_id='tenant-1', capability_key='create_listing', feedback={'executed': True, 'verified': True})
    report = recovered.run(make_request(goal='Recover verified listing publication', max_steps=1, meta={'runtime_capabilities': {'create_listing': {'enabled': True, 'healthy': True, 'health_score': 0.98}}}, approval_policy={'allow_action_types': ['create_listing']}))
    owner_path = dict(report.final_feedback['owner_path'])
    assert report.completed is True
    assert owner_path['second_brain_blocked'] is True
    assert owner_path['resumed_from_previous_run'] is True
    assert owner_path['observation_count'] >= 3
    assert owner_path['stage_observation_counts']['routing'] >= 2
    assert owner_path['stage_observation_counts']['verification'] >= 1
def test_owner_path_survives_multi_cycle_chain(tmp_path) -> None:
    shared = tmp_path / 'shared-chain'
    phases = [
        ({'verified': False, 'goal_reached': False}, {'create_listing': {'enabled': True, 'healthy': True, 'health_score': 0.95}}),
        ({'verified': False, 'goal_reached': False}, {'create_listing': {'enabled': True, 'healthy': False, 'health_score': 0.10}}),
        ({'verified': True, 'goal_reached': True, 'terminal': True, 'external_refs': ['listing:1']}, {'create_listing': {'enabled': True, 'healthy': True, 'health_score': 0.99}}),
        ({'verified': True, 'goal_reached': True, 'terminal': True, 'external_refs': ['listing:2']}, {'create_listing': {'enabled': True, 'healthy': True, 'health_score': 1.0}}),
    ]
    final_report = None
    for output, caps in phases:
        harness = build_harness(shared, scenario=[ScenarioStep(action_type='create_listing' if output.get('verified') else 'notify_owner', output=output)], runtime_capabilities=caps)
        final_report = harness.run(make_request(goal='Publish listing through one canonical path', max_steps=1, approval_policy={'allow_action_types': ['create_listing']}, meta={'runtime_capabilities': caps}))
    owner_path = dict(final_report.final_feedback['owner_path'])
    assert owner_path['second_brain_blocked'] is True
    assert owner_path['resumed_from_previous_run'] is True
    assert owner_path['observation_count'] >= 4
    assert owner_path['stage_observation_counts']['planner'] >= 4
