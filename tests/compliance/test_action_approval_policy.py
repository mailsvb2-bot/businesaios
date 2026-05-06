from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy
from compliance.approval_compliance_policy import ApprovalComplianceInput, ApprovalCompliancePolicy


def test_autonomous_destructive_action_requires_operator() -> None:
    policy = ActionCompliancePolicy()
    verdict = policy.evaluate(
        ActionComplianceInput(
            action_type='delete_campaign',
            action_scope='marketing',
            actor_type='autonomous',
            tenant_id='t1',
            region='eu',
            connector_name='ads',
            destructive=True,
            outbound_effect=True,
        )
    )
    assert verdict.allowed is True
    assert verdict.operator_required is True


def test_cross_region_pii_transfer_requires_reviews() -> None:
    approval = ApprovalCompliancePolicy()
    verdict = approval.evaluate(
        ApprovalComplianceInput(
            action=ActionComplianceInput(
                action_type='export_evidence',
                action_scope='compliance',
                actor_type='human',
                tenant_id='t1',
                region='eu',
                connector_name='storage',
                contains_pii=True,
            ),
            external_data_transfer=True,
            cross_region_transfer=True,
        )
    )
    assert verdict.allowed is True
    assert 'privacy' in verdict.required_reviews
    assert 'legal' in verdict.required_reviews
