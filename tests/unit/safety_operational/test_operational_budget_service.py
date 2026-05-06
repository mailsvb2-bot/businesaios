from __future__ import annotations

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.operational.factory import build_operational_safety_runtime


def test_publication_is_counted_by_code_not_by_name_heuristic() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="publish_listing@v1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.impact.publication_count == 1
    assert result.impact.outbound_count == 0
    assert result.decision.status == "allow"


def test_outbound_is_counted_by_registry_spec() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="send_email_outreach@v1",
            payload={"recipient_count": 3, "safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.impact.outbound_count == 3
    assert result.impact.cost_minor == 15
    assert result.decision.status == "allow"


def test_strategic_change_without_human_approval_is_blocked_by_policy() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="change_pricing@v1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.impact.strategic_change_count == 1
    assert result.decision.status == "block"
    assert result.decision.reason == "human_approval_required"


def test_human_approved_strategic_change_can_pass_precheck() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="change_pricing@v1",
            payload={"human_approved": True, "safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.decision.status == "allow"


def test_hourly_limit_blocks_third_action() -> None:
    runtime = build_operational_safety_runtime()

    first = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="read_metrics@v1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    runtime.service.commit(first.envelope)

    runtime.ledger.commit(
        "tenant-1",
        execution_id=None,
        hour_bucket="2026-03-21T10",
        day_bucket="2026-03-21",
        actions_count=23,
        budget_minor=0,
        publications_count=0,
        outbound_count=0,
        strategic_changes_without_approval=0,
        rollback_triggers=0,
    )

    second = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="read_metrics@v1",
            payload={"safety_now": "2026-03-21T10:05:00+00:00"},
        )
    )
    assert second.decision.status == "allow"
    runtime.service.commit(second.envelope)

    third = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="read_metrics@v1",
            payload={"safety_now": "2026-03-21T10:10:00+00:00"},
        )
    )
    assert third.decision.status == "block"
    assert third.decision.details["exceeded"]["max_actions_per_hour"] is True


def test_unknown_action_is_fail_closed_and_blocked() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="totally_unknown_action@v1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.impact.category.value == "unknown"
    assert result.impact.confidence == 0.0
    assert result.decision.status == "block"
    assert result.decision.reason == "human_approval_required"


def test_rollback_requires_human_approval_even_when_not_strategic() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="rollback_campaign@v1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert result.decision.status == "block"
    assert result.decision.reason == "human_approval_required"


def test_commit_is_idempotent_by_execution_id() -> None:
    runtime = build_operational_safety_runtime()
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="tenant-1",
            user_id="user-1",
            action_name="read_metrics@v1",
            execution_id="exec-1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    runtime.service.commit(result.envelope)
    runtime.service.commit(result.envelope)

    hour = runtime.ledger.get_hour("tenant-1", "2026-03-21T10")
    day = runtime.ledger.get_day("tenant-1", "2026-03-21")
    assert hour.actions_count == 1
    assert day.actions_count == 1