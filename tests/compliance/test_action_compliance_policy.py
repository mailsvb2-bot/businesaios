from __future__ import annotations

from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy
from compliance.base import ComplianceControl, ComplianceVerdictStatus


def test_action_compliance_policy_requires_operator_for_autonomous_restricted_change() -> None:
    policy = ActionCompliancePolicy()
    verdict = policy.evaluate(
        ActionComplianceInput(
            action_type='rotate_keys',
            action_scope='security',
            actor_type='autonomous',
            tenant_id='tenant-a',
            region='eu',
            connector_name='vault',
            contains_secrets=True,
            destructive=True,
            outbound_effect=True,
        )
    )

    assert verdict.status is ComplianceVerdictStatus.OPERATOR_REQUIRED
    assert verdict.operator_required is True
    assert ComplianceControl.SECRET_REDACTION in verdict.required_controls
    assert ComplianceControl.APPROVAL in verdict.required_controls
    assert 'scope:security' in verdict.compliance_tags


def test_action_compliance_policy_denies_forbidden_action_type() -> None:
    policy = ActionCompliancePolicy(forbidden_action_types=('drop_database',))
    verdict = policy.evaluate(
        ActionComplianceInput(
            action_type='drop_database',
            action_scope='billing',
            actor_type='human',
            tenant_id='tenant-a',
            region='eu',
            connector_name='postgres',
        )
    )

    assert verdict.status is ComplianceVerdictStatus.DENIED
    assert 'forbidden_action_type' in verdict.blocked_by


def test_action_compliance_policy_requires_evidence_for_normal_allowed_actions() -> None:
    policy = ActionCompliancePolicy()
    verdict = policy.evaluate(
        ActionComplianceInput(
            action_type='sync_customer',
            action_scope='crm',
            actor_type='human',
            tenant_id='tenant-a',
            region='eu',
            connector_name='hubspot',
            evidence_required=True,
        )
    )

    assert verdict.status is ComplianceVerdictStatus.ALLOWED
    assert ComplianceControl.EVIDENCE_VERIFICATION in verdict.required_controls


def test_action_compliance_policy_denies_empty_action_shape_fail_closed() -> None:
    policy = ActionCompliancePolicy()
    verdict = policy.evaluate(
        ActionComplianceInput(
            action_type='   ',
            action_scope='   ',
            actor_type='human',
            tenant_id='tenant-a',
            region='eu',
            connector_name='x',
        )
    )

    assert verdict.status is ComplianceVerdictStatus.DENIED
    assert set(verdict.blocked_by) == {'empty_action_scope', 'empty_action_type'}
