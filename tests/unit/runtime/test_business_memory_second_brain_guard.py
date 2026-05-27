from __future__ import annotations

from types import SimpleNamespace

from application.headless.feedback import SimpleHeadlessFeedbackReader
from execution.business_memory_query import BusinessMemoryQueryService
from execution.business_operating_memory import FileBusinessOperatingMemoryStore
from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload


def test_sanitize_business_memory_payload_removes_second_brain_vectors() -> None:
    payload = sanitize_business_memory_payload({
        "blocked_actions": ["ACTION_LAUNCH_CAMPAIGN"],
        "autonomy_tier": "full_autonomy",
        "budget_envelope": {"cap": 100},
        "learned_preferences": {"preferred_channels": ["seo"], "preferred_action_types": ["ACTION_CREATE_LISTING"]},
        "operating_constraints": {"constraint_keys": ["budget_cap"], "blocked_actions": ["ACTION_ROUTE_LEAD"]},
    })

    assert "blocked_actions" not in payload
    assert "autonomy_tier" not in payload
    assert "budget_envelope" not in payload
    assert payload["learned_preferences"] == {"preferred_channels": ["seo"]}
    assert payload["operating_constraints"] == {"constraint_keys": ["budget_cap"]}


def test_business_memory_query_service_strips_action_guidance(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow demand",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"status": "verified", "goal_reached": True},
        step_count=1,
        profile={"segment": "services"},
        constraints={},
        signals=[],
        meta={"preferred_action_types": ["ACTION_CREATE_LISTING"]},
        channel="seo",
        region="eu",
        product_name="growth",
    )

    query = BusinessMemoryQueryService(store=store)
    summary = query.get_summary(tenant_id="tenant-1", business_id="biz-1")
    assert "preferred_action_types" not in summary["learned_preferences"]


def test_headless_feedback_reader_does_not_turn_business_memory_into_decider() -> None:
    reader = SimpleHeadlessFeedbackReader.default()
    request = SimpleNamespace(goal="grow", meta={"business_memory": {"blocked_actions": ["ACTION_SEND_EMAIL"]}}, ceo=None)
    envelope = SimpleNamespace(decision=SimpleNamespace(payload={}, decision_id="dec-1", action="send_email"))
    action = SimpleNamespace(action_id="act-1", action_type="ACTION_SEND_EMAIL")
    action_result = SimpleNamespace(payload={}, attempted=True, executed=True, verified=True, operator_required=False, status="executed")
    result = SimpleNamespace(output={"goal_reached": True, "terminal": True}, error=None)

    feedback = reader.read(
        request=request,
        state=None,
        envelope=envelope,
        executable_action=action,
        action_result=action_result,
        result=result,
        step_index=0,
    )

    assert feedback["goal_reached"] is True
    assert "blocked_actions" not in feedback["business_memory_before_step"]


def test_sanitize_business_memory_payload_removes_nested_action_guidance_keys() -> None:
    payload = sanitize_business_memory_payload({
        "learned_preferences": {
            "preferred_channels": ["seo"],
            "next_action": "launch_campaign",
            "nested": {"recommended_action": "route_lead", "keep": True},
        },
        "operating_constraints": {
            "constraint_keys": ["budget_cap"],
            "nested": {"next_action": "launch_campaign", "keep": "yes"},
        },
    })

    assert payload["learned_preferences"] == {"preferred_channels": ["seo"], "nested": {"keep": True}}
    assert payload["operating_constraints"] == {"constraint_keys": ["budget_cap"], "nested": {"keep": "yes"}}


def test_sanitize_business_memory_payload_removes_casefolded_action_guidance_keys() -> None:
    payload = sanitize_business_memory_payload({
        "Blocked_Actions": ["ACTION_LAUNCH_CAMPAIGN"],
        "learned_preferences": {"Recommended_Action": "route_lead", "channel": "seo"},
        "operating_constraints": {"Next_Action": "launch_campaign", "constraint_keys": ["budget_cap"]},
    })

    assert "Blocked_Actions" not in payload
    assert payload["learned_preferences"] == {"channel": "seo"}
    assert payload["operating_constraints"] == {"constraint_keys": ["budget_cap"]}



def test_sanitize_business_memory_payload_removes_action_guidance_from_arbitrary_nested_sections() -> None:
    payload = sanitize_business_memory_payload({
        "analytics": {
            "next_action": "launch_campaign",
            "nested": {"Recommended_Action": "route_lead", "keep": 1},
        },
        "recent_runs": [
            {"run_id": "r1", "summary": "ok", "operator_overrides": {"approve": True}},
        ],
    })

    assert payload["analytics"] == {"nested": {"keep": 1}}
    assert payload["recent_runs"] == [{"run_id": "r1", "summary": "ok"}]


def test_business_memory_policy_feedback_sanitization_strips_nested_action_guidance() -> None:
    from execution.business_memory_policy import BusinessMemoryPolicy

    payload = BusinessMemoryPolicy().sanitize_feedback_payload({
        'decision_hint': {'next_action': 'launch_campaign', 'priority': 10},
        'history': [{'recommended_action': 'route_lead', 'keep': True}],
    })

    assert payload['decision_hint'] == {'priority': 10}
    assert payload['history'] == [{'keep': True}]
