from __future__ import annotations

from typing import Any


def assert_feedback_contract_shape(feedback: dict[str, Any]) -> None:
    required = {
        "attempted",
        "executed",
        "verified",
        "operator_required",
        "verification_status",
        "verification_confidence",
        "goal_evaluation",
        "policy_explanation",
        "autonomy_audit",
        "capability_planning",
        "self_healing_retry",
        "recent_actions",
    }
    missing = sorted(required.difference(feedback))
    assert not missing, f"missing feedback keys: {missing}"
    assert isinstance(feedback["attempted"], bool)
    assert isinstance(feedback["executed"], bool)
    assert isinstance(feedback["verified"], bool)
    assert isinstance(feedback["operator_required"], bool)
    assert isinstance(feedback["goal_evaluation"], dict)
    assert isinstance(feedback["policy_explanation"], dict)
    assert isinstance(feedback["autonomy_audit"], dict)
    assert isinstance(feedback["capability_planning"], dict)
    assert isinstance(feedback["self_healing_retry"], dict)
    assert isinstance(feedback["recent_actions"], list)


def assert_step_report_consistency(step: Any) -> None:
    assert step.action
    assert step.action_id
    assert step.decision_id
    assert step.status
    assert isinstance(step.payload, dict)
    assert isinstance(step.feedback, dict)
    assert isinstance(step.execution_feedback, dict)
    assert isinstance(step.canonical_step_artifact, dict)
    artifact = step.canonical_step_artifact
    assert artifact.get("action_type") == step.action
    assert artifact.get("action_id") == step.action_id
    assert artifact.get("decision_id") == step.decision_id
    assert artifact.get("status") == step.status
    if step.verified:
        assert step.executed is True
        assert step.attempted is True


def assert_report_ledger_snapshot_consistency(*, report: Any, ledger: dict[str, Any], snapshot: dict[str, Any]) -> None:
    assert ledger["goal"] == report.goal
    assert ledger["business_id"] == report.business_id
    assert ledger["tenant_id"] == report.tenant_id
    assert ledger["completed"] == report.completed
    assert ledger["stop_reason"] == report.stop_reason
    assert ledger["steps_count"] == len(report.steps)
    assert ledger["canonical_run_artifact"]["goal"] == report.canonical_run_artifact["goal"]
    assert ledger["canonical_run_artifact"]["business_id"] == report.business_id
    assert ledger["canonical_run_artifact"]["tenant_id"] == report.tenant_id
    assert snapshot["goal"] == report.goal
    assert snapshot["tenant_id"] == report.tenant_id
    assert snapshot["business_id"] == report.business_id


def assert_recent_actions_deduped(feedback: dict[str, Any]) -> None:
    rows = list(feedback.get("recent_actions") or [])
    seen: set[str] = set()
    for row in rows:
        if row.get("action_id"):
            key = f"action:{row['action_id']}"
        elif row.get("decision_id"):
            key = f"decision:{row['decision_id']}"
        else:
            key = f"{row.get('action_type')}|{row.get('status')}|{row.get('step_index')}"
        assert key not in seen, f"duplicate recent action key: {key}"
        seen.add(key)
