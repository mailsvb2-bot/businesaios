from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
import execution.approval_execution_gate as approval_gate_module
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyDecision, ApprovalPolicyEngine
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy


def _ctx() -> ActionExecutionContext:
    return ActionExecutionContext(
        tenant_id='tenant-1',
        user_id='user-1',
        execution_id='execution-1',
        action_name='send_email',
        payload={},
        metadata={'decision_id': 'decision-1'},
    )


def _impact() -> ActionImpact:
    return ActionImpact(action_name='send_email', category=ActionCategory.OUTBOUND, outbound_count=1)


def _gate() -> ApprovalExecutionGate:
    return ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()),
        approval_workflow=ApprovalWorkflow(store=InMemoryApprovalStore()),
    )


def test_invalid_execution_id_contract_becomes_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval_gate_module,
        '_require_execution_id',
        lambda _ctx: (_ for _ in ()).throw(RuntimeError('missing execution id')),
    )

    verdict = _gate().evaluate(ctx=_ctx(), impact=_impact(), metadata={'decision_id': 'decision-1'})

    assert verdict.allowed is False
    assert verdict.reason == 'approval_gate_invalid_execution_id:RuntimeError'


def test_execution_id_dependency_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval_gate_module,
        '_require_execution_id',
        lambda _ctx: (_ for _ in ()).throw(OSError('execution identity store unavailable')),
    )

    with pytest.raises(OSError, match='execution identity store unavailable'):
        _gate().evaluate(ctx=_ctx(), impact=_impact(), metadata={'decision_id': 'decision-1'})


def test_fingerprint_validation_error_becomes_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval_gate_module,
        'build_execution_subject_fingerprint',
        lambda **_kwargs: (_ for _ in ()).throw(ValueError('invalid subject')),
    )

    verdict = _gate().evaluate(ctx=_ctx(), impact=_impact(), metadata={'decision_id': 'decision-1'})

    assert verdict.allowed is False
    assert verdict.reason == 'approval_gate_subject_fingerprint_error:ValueError'


def test_fingerprint_backend_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval_gate_module,
        'build_execution_subject_fingerprint',
        lambda **_kwargs: (_ for _ in ()).throw(OSError('fingerprint backend unavailable')),
    )

    with pytest.raises(OSError, match='fingerprint backend unavailable'):
        _gate().evaluate(ctx=_ctx(), impact=_impact(), metadata={'decision_id': 'decision-1'})


def _policy() -> ApprovalPolicyDecision:
    return ApprovalPolicyDecision(
        approval_required=True,
        operator_required=True,
        manual_override_allowed=True,
        auto_submit_approval=True,
        approval_scope='execution',
        metadata={'autonomy_tier': 'supervised'},
    )


def _override(error: Exception) -> SimpleNamespace:
    return SimpleNamespace(
        request=SimpleNamespace(override_id='override-1'),
        approved_once=False,
        validate_binding=lambda **_kwargs: (_ for _ in ()).throw(error),
    )


def test_operator_override_contract_error_becomes_denial() -> None:
    verdict = _gate()._evaluate_operator_override(
        operator_override=_override(RuntimeError('binding mismatch')),
        policy=_policy(),
        ctx=_ctx(),
        execution_id='execution-1',
        decision_id='decision-1',
        subject_fingerprint='fingerprint-1',
    )

    assert verdict is not None
    assert verdict.allowed is False
    assert verdict.reason == 'operator_override_invalid:RuntimeError'


def test_operator_override_dependency_failure_is_visible() -> None:
    with pytest.raises(OSError, match='override store unavailable'):
        _gate()._evaluate_operator_override(
            operator_override=_override(OSError('override store unavailable')),
            policy=_policy(),
            ctx=_ctx(),
            execution_id='execution-1',
            decision_id='decision-1',
            subject_fingerprint='fingerprint-1',
        )
