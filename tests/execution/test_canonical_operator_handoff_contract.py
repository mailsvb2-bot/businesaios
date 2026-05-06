from __future__ import annotations

from execution.canonical_operator_handoff import canonical_operator_handoff, canonical_operator_resolution
from execution.operator_handoff_policy import OperatorHandoffPolicy


class _Trace:
    run_id = 'run-1'


class _Envelope:
    class decision:
        decision_id = 'dec-1'
        action = 'ads.update_budget'


class _Request:
    autonomy_tier = 'supervised'


class _Retry:
    reason = 'operator_required'


class _Autonomy:
    handoff_reason = 'approval_needed'
    approval_required = True
    blocked_by_policy = False


def test_canonical_operator_handoff_normalizes_state_and_reasons() -> None:
    payload = canonical_operator_handoff(
        {
            'run_id': 'run-1',
            'step_index': 2,
            'decision_id': 'dec-1',
            'action': 'crm.write_record',
            'autonomy_tier': 'supervised',
            'reason': 'operator_required',
            'handoff_reason': 'approval_needed',
            'next_tier': 'bounded_autonomy',
            'handoff_state': 'weird-value',
        }
    )
    assert payload['handoff_state'] == 'handoff_required'
    assert payload['escalation_required'] is True
    assert 'approval_needed' in payload['reasons']


def test_operator_handoff_policy_builds_canonical_payload() -> None:
    policy = OperatorHandoffPolicy()
    payload = policy.build_payload(
        trace=_Trace(),
        step_index=1,
        envelope=_Envelope(),
        request=_Request(),
        retry_info=_Retry(),
        autonomy_decision=_Autonomy(),
        feedback={'verified': False, 'next_tier_context': {'suggested_tier': 'bounded_autonomy'}},
    )
    assert payload['run_id'] == 'run-1'
    assert payload['handoff_state'] == 'awaiting_operator'
    assert payload['next_tier'] == 'bounded_autonomy'


def test_operator_resolution_normalizes_manual_override() -> None:
    handoff = canonical_operator_handoff({'run_id': 'run-1', 'step_index': 1, 'decision_id': 'dec-1', 'action': 'x'})
    result = canonical_operator_resolution(handoff, resolution='manual_override', note='ok')
    assert result['manual_override_used'] is True
    assert result['handoff_state'] == 'resolved'
