from __future__ import annotations

from application.autonomy.autonomy_safety_bundle import AutonomySafetyBundle
from execution.canonical_autonomy_safety import canonical_autonomy_safety_decision


class _Request:
    autonomy_tier = 'bounded_autonomy'
    approval_policy = {}
    constraints = {}
    economy = {}


def test_canonical_autonomy_safety_decision_projects_operator_handoff_trigger() -> None:
    payload = canonical_autonomy_safety_decision(
        request=_Request(),
        safety_verdict={'allowed': False, 'operator_required': True, 'reason': 'bounded_autonomy_exceeded'},
        bounded_autonomy={'reason': 'bounded_autonomy_exceeded', 'operator_required': True},
        blast_radius_guard={'allowed': True, 'reason': 'within_blast_radius'},
        safe_self_driving={'should_stop': False, 'should_downgrade': False},
        next_tier_context={'suggested_tier': 'supervised'},
    )
    assert payload['blocked'] is True
    assert payload['handoff_triggered'] is True
    assert payload['next_tier'] == 'supervised'


def test_policy_snapshot_includes_canonical_autonomy_safety_decision() -> None:
    snapshot = AutonomySafetyBundle.build_policy_snapshot(
        request=_Request(),
        safety_verdict={'allowed': True, 'operator_required': False, 'reason': 'within', 'next_tier': 'bounded_autonomy', 'details': {}},
    )
    assert 'autonomy_safety_decision' in snapshot
    assert snapshot['autonomy_safety_decision']['next_tier'] == 'bounded_autonomy'
