from __future__ import annotations

from runtime.platform.business_memory.service import BusinessMemoryService
from runtime.platform.business_memory.store import FileBusinessMemoryStore


def test_business_memory_service_compacts_recent_runs_and_derives_recurring_patterns(tmp_path) -> None:
    service = BusinessMemoryService(store=FileBusinessMemoryStore(root_dir=tmp_path / 'memory'))
    for idx in range(30):
        service.update_after_step(
            business_id='biz-1',
            action_type='ACTION_CREATE_LISTING',
            feedback={
                'verified': True,
                'verification_status': 'verified',
                'external_refs': [f'listing-{idx % 3}'],
                'normalized_outcome': {'lead_count': 1, 'channel': 'seo'},
                'goal_score': 0.9,
                'channel': 'seo',
            },
            request_meta={
                'goal': 'grow demand',
                'constraints': {'budget_cap': 1000, 'geo': 'nl'},
                'autonomy_tier': 'supervised',
            },
        )

    payload = service.get(business_id='biz-1')
    assert payload['recent_runs_count'] <= 20
    assert payload['recurring_wins'][0]['action'] == 'ACTION_CREATE_LISTING'
    assert payload['recurring_wins'][0]['count'] >= 2
    assert payload['learned_preferences']['preferred_channels'][0] == 'seo'
    assert 'grow demand' in payload['active_goals']
    assert 'budget_cap' in payload['operating_constraints']['constraint_keys']
    assert payload['aggregated_business_profile']['verified_outcomes_count'] <= 20


def test_business_memory_service_derives_recurring_failures_without_json_bloat(tmp_path) -> None:
    service = BusinessMemoryService(store=FileBusinessMemoryStore(root_dir=tmp_path / 'memory'))
    for _ in range(6):
        service.update_after_step(
            business_id='biz-2',
            action_type='ACTION_LAUNCH_CAMPAIGN',
            feedback={
                'verified': False,
                'verification_status': 'unverified',
                'error': 'approval_required',
                'retry_classification': {'kind': 'operator_required', 'reason': 'approval_required'},
            },
            request_meta={'goal': 'launch growth', 'constraints': {'approval_gate': True}},
        )

    payload = service.get(business_id='biz-2')
    assert payload['recent_runs_count'] <= 20
    assert payload['recurring_failures'][0]['action'] == 'ACTION_LAUNCH_CAMPAIGN'
    assert payload['recurring_failures'][0]['count'] >= 2
    assert 'blocked_actions' not in payload
    assert 'blocked_actions' not in payload['operating_constraints']


def test_business_memory_service_strips_action_guidance_from_runtime_payload(tmp_path) -> None:
    service = BusinessMemoryService(store=FileBusinessMemoryStore(root_dir=tmp_path / 'memory'))
    service.update_after_step(
        business_id='biz-3',
        action_type='ACTION_ROUTE_LEAD',
        feedback={
            'verified': True,
            'verification_status': 'verified',
            'normalized_outcome': {'channel': 'email'},
            'channel': 'email',
        },
        request_meta={
            'goal': 'convert more leads',
            'autonomy_tier': 'bounded_autonomy',
            'budget_envelope': {'cap': 100},
            'operator_overrides': {'approve': True},
            'constraints': {'approval_gate': True},
        },
    )

    payload = service.get(business_id='biz-3')
    assert 'autonomy_tier' not in payload
    assert 'budget_envelope' not in payload
    assert 'operator_overrides' not in payload
    assert 'preferred_action_types' not in payload['learned_preferences']
