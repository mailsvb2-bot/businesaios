from __future__ import annotations

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from execution.approval_execution_gate import build_execution_subject_fingerprint


def _impact() -> ActionImpact:
    return ActionImpact(action_name="send_email", category=ActionCategory.OUTBOUND, outbound_count=1, confidence=0.9)


def test_fingerprint_ignores_transient_metadata_fields() -> None:
    base = ActionExecutionContext(
        tenant_id="tenant-a",
        user_id="user-1",
        action_name="send_email",
        payload={"channel": "email", "body": "hello", "meta": {"tags": ["ops"], "trace_id": "trace-1", "expires_at": "soon"}},
        metadata={"decision_id": "dec-1", "tags": ["ops"], "trace_id": "trace-1", "expires_at": "soon"},
        execution_id="exec-1",
    )
    changed = ActionExecutionContext(
        tenant_id="tenant-a",
        user_id="user-1",
        action_name="send_email",
        payload={"channel": "email", "body": "hello", "meta": {"tags": ["ops"], "trace_id": "trace-99", "expires_at": "later"}},
        metadata={"decision_id": "dec-1", "tags": ["ops"], "trace_id": "trace-99", "expires_at": "later", "approval_request_fingerprint": "fp-x"},
        execution_id="exec-1",
    )
    fp1 = build_execution_subject_fingerprint(ctx=base, decision_id="dec-1", impact=_impact(), external_confirmation_mode="required")
    fp2 = build_execution_subject_fingerprint(ctx=changed, decision_id="dec-1", impact=_impact(), external_confirmation_mode="required")
    assert fp1 == fp2
