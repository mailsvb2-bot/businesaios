from compliance.action_compliance_policy import ActionComplianceInput
from compliance.compliance_bundle import ComplianceBundle, ComplianceBundleInput
from compliance.connector_compliance_matrix import (
    ConnectorComplianceMatrix,
    ConnectorComplianceRecord,
    ConnectorRiskTier,
)
from compliance.data_classification import DataAsset


def test_bundle_denies_when_connector_not_registered() -> None:
    bundle = ComplianceBundle()
    verdict = bundle.evaluate(
        ComplianceBundleInput(
            data_asset=DataAsset(
                asset_id='a1',
                name='customer email export',
                content_type='application/json',
                region_hint='eu',
            ),
            action=ActionComplianceInput(
                action_type='export',
                action_scope='compliance',
                actor_type='human',
                tenant_id='t1',
                region='eu',
                connector_name='unknown',
                outbound_effect=True,
            ),
            target_region='eu',
        )
    )
    assert verdict.allowed is False


def test_bundle_allows_registered_connector() -> None:
    matrix = ConnectorComplianceMatrix(
        records={
            'storage': ConnectorComplianceRecord(
                connector_name='storage',
                risk_tier=ConnectorRiskTier.MODERATE,
                regions_allowed=('eu',),
                supports_audit=True,
                supports_redaction=True,
                supports_scoped_credentials=True,
                supports_data_deletion=True,
                approved_for_pii=True,
                approved_for_secrets=True,
            )
        }
    )
    bundle = ComplianceBundle(connector_matrix=matrix)
    verdict = bundle.evaluate(
        ComplianceBundleInput(
            data_asset=DataAsset(
                asset_id='a1',
                name='customer email export',
                content_type='application/json',
                region_hint='eu',
            ),
            action=ActionComplianceInput(
                action_type='export',
                action_scope='compliance',
                actor_type='human',
                tenant_id='t1',
                region='eu',
                connector_name='storage',
                outbound_effect=True,
            ),
            target_region='eu',
        )
    )
    assert verdict.connector.allowed is True
