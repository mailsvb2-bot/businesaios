from compliance.connector_compliance_matrix import (
    ConnectorComplianceMatrix,
    ConnectorComplianceRecord,
    ConnectorRiskTier,
)


def test_unregistered_connector_denied() -> None:
    matrix = ConnectorComplianceMatrix()
    decision = matrix.evaluate(
        connector_name='unknown',
        target_region='eu',
        contains_pii=False,
        contains_secrets=False,
    )
    assert decision.allowed is False


def test_registered_pii_capable_connector_allowed() -> None:
    matrix = ConnectorComplianceMatrix(
        records={
            'crm': ConnectorComplianceRecord(
                connector_name='crm',
                risk_tier=ConnectorRiskTier.MODERATE,
                regions_allowed=('eu',),
                supports_audit=True,
                supports_redaction=True,
                supports_scoped_credentials=True,
                supports_data_deletion=True,
                approved_for_pii=True,
                approved_for_secrets=False,
            )
        }
    )
    decision = matrix.evaluate(
        connector_name='crm',
        target_region='eu',
        contains_pii=True,
        contains_secrets=False,
    )
    assert decision.allowed is True
