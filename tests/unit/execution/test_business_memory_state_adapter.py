from execution.business_memory_state_adapter import BusinessMemoryStateAdapter
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.models import GoalExecutionRequest


def test_business_memory_state_adapter_projects_evidence_only_context() -> None:
    adapter = BusinessMemoryStateAdapter()
    payload = adapter.to_state_context(
        {
            'recurring_failures': [{'action': 'A', 'count': 3}],
            'recurring_wins': [{'action': 'B', 'count': 2}],
            'learned_preferences': {'preferred_channels': ['seo']},
            'active_goals': ['grow demand'],
            'operating_constraints': {'constraint_keys': ['budget_cap']},
            'aggregated_business_profile': {'verified_outcomes_count': 5},
        }
    )
    assert payload['evidence_only'] is True
    assert payload['must_not_issue_decision'] is True
    assert payload['recurring_failures'][0]['action'] == 'A'


def test_headless_goal_mapper_injects_business_memory_evidence_into_world_state() -> None:
    mapper = HeadlessGoalStateMapper()
    state = mapper.to_world_state(
        request=GoalExecutionRequest(
            goal='grow demand',
            business_id='biz-1',
            tenant_id='tenant-1',
            meta={'business_memory': {'recurring_wins': [{'action': 'ACTION_CREATE_LISTING', 'count': 2}]}}
        ),
        step_index=0,
        previous_feedback={},
    )
    evidence = state.meta['business_memory_evidence']
    assert evidence['evidence_only'] is True
    assert evidence['recurring_wins'][0]['action'] == 'ACTION_CREATE_LISTING'


def test_business_memory_state_adapter_normalizes_malformed_payload_via_canonical_memory() -> None:
    adapter = BusinessMemoryStateAdapter()
    payload = adapter.to_state_context(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "recurring_failures": ["timeout", {"key": "verification_failed", "count": "2"}],
            "learned_preferences": {"Preferred_Action_Types": ["ACTION_SEND_EMAIL"], "channel": "seo"},
            "active_goals": ["grow demand", "grow demand"],
            "average_goal_score": 1.9,
        }
    )

    assert payload["tenant_id"] == "tenant-1"
    assert payload["business_id"] == "biz-1"
    assert payload["recurring_failures"][0]["key"] == "timeout"
    assert payload["learned_preferences"] == {"channel": "seo"}
    assert payload["active_goals"] == ["grow demand"]
    assert payload["average_goal_score"] == 0.0



def test_business_memory_state_adapter_uses_canonical_state_projection_and_strips_guidance() -> None:
    adapter = BusinessMemoryStateAdapter()
    payload = adapter.to_state_context(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "recurring_failures": [{"key": "timeout", "count": 2}],
            "anti_patterns": [{"key": "verification_failed", "confidence": 0.8}],
            "learned_preferences": {"channel": "seo", "next_action": "launch_campaign"},
            "aggregated_business_profile": {"segment": "services", "operator_overrides": {"approve": True}},
        }
    )

    assert payload["recurring_failures"][0]["action"] == "timeout"
    assert payload["anti_patterns"][0]["action"] == "verification_failed"
    assert payload["learned_preferences"] == {"channel": "seo"}
    assert payload["aggregated_business_profile"] == {"segment": "services"}
