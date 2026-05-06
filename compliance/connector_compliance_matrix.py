from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from compliance.base import ComplianceControl, PolicyMetadata


class ConnectorRiskTier(str, Enum):
    LOW = 'low'
    MODERATE = 'moderate'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass(frozen=True)
class ConnectorComplianceRecord:
    connector_name: str
    risk_tier: ConnectorRiskTier
    regions_allowed: tuple[str, ...]
    supports_audit: bool
    supports_redaction: bool
    supports_scoped_credentials: bool
    supports_data_deletion: bool
    approved_for_pii: bool = False
    approved_for_secrets: bool = False
    approved_for_cross_region_transfer: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorComplianceDecision:
    allowed: bool
    reason: str
    required_controls: tuple[ComplianceControl, ...]
    connector_name: str
    risk_tier: ConnectorRiskTier
    policy: PolicyMetadata


class ConnectorComplianceMatrix:
    def __init__(
        self,
        records: Optional[Mapping[str, ConnectorComplianceRecord]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._policy = PolicyMetadata(
            policy_name='connector_compliance_matrix',
            policy_version=policy_version,
            tags=('connector', 'capability', 'compliance'),
        )
        self._records = {k.lower(): v for k, v in (records or {}).items()}

    def register(self, record: ConnectorComplianceRecord) -> None:
        self._records[record.connector_name.lower()] = record

    def get(self, connector_name: str) -> Optional[ConnectorComplianceRecord]:
        return self._records.get(connector_name.lower())

    def evaluate(
        self,
        *,
        connector_name: str,
        target_region: Optional[str],
        contains_pii: bool,
        contains_secrets: bool,
        cross_region_transfer: bool = False,
    ) -> ConnectorComplianceDecision:
        record = self.get(connector_name)
        if record is None:
            return ConnectorComplianceDecision(
                allowed=False,
                reason='Connector is not registered in compliance matrix.',
                required_controls=(),
                connector_name=connector_name,
                risk_tier=ConnectorRiskTier.CRITICAL,
                policy=self._policy,
            )

        controls: list[ComplianceControl] = []
        normalized_target_region = (target_region or '').strip().lower()
        if normalized_target_region and record.regions_allowed:
            if normalized_target_region not in {r.strip().lower() for r in record.regions_allowed}:
                return ConnectorComplianceDecision(
                    allowed=False,
                    reason='Connector is not approved for target region.',
                    required_controls=(),
                    connector_name=record.connector_name,
                    risk_tier=record.risk_tier,
                    policy=self._policy,
                )
        if cross_region_transfer and not record.approved_for_cross_region_transfer:
            return ConnectorComplianceDecision(
                allowed=False,
                reason='Connector is not approved for cross-region transfer.',
                required_controls=(),
                connector_name=record.connector_name,
                risk_tier=record.risk_tier,
                policy=self._policy,
            )
        if contains_pii:
            if not record.approved_for_pii:
                return ConnectorComplianceDecision(
                    allowed=False,
                    reason='Connector is not approved for PII-bearing data.',
                    required_controls=(),
                    connector_name=record.connector_name,
                    risk_tier=record.risk_tier,
                    policy=self._policy,
                )
            controls.append(ComplianceControl.PII_MINIMIZATION)
        if contains_secrets:
            if not record.approved_for_secrets:
                return ConnectorComplianceDecision(
                    allowed=False,
                    reason='Connector is not approved for secret-bearing payloads.',
                    required_controls=(),
                    connector_name=record.connector_name,
                    risk_tier=record.risk_tier,
                    policy=self._policy,
                )
            controls.append(ComplianceControl.SECRET_SCOPE_ENFORCEMENT)
        if not record.supports_audit:
            return ConnectorComplianceDecision(
                allowed=False,
                reason='Connector lacks required audit capability.',
                required_controls=(),
                connector_name=record.connector_name,
                risk_tier=record.risk_tier,
                policy=self._policy,
            )
        if not record.supports_scoped_credentials:
            controls.append(ComplianceControl.SECRET_SCOPE_ENFORCEMENT)
        if contains_pii and not record.supports_redaction:
            controls.append(ComplianceControl.UPSTREAM_REDACTION_REQUIRED)
        if contains_pii and not record.supports_data_deletion:
            controls.append(ComplianceControl.RETENTION_EXCEPTION_REVIEW)

        return ConnectorComplianceDecision(
            allowed=True,
            reason='Connector passed compliance capability evaluation.',
            required_controls=tuple(sorted(set(controls), key=lambda x: x.value)),
            connector_name=record.connector_name,
            risk_tier=record.risk_tier,
            policy=self._policy,
        )
