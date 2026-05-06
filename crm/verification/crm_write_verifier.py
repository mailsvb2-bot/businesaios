from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_verification_contract import CrmVerificationRequest, CrmVerificationResult


class CrmWriteVerifier:
    def verify(self, connector: CrmConnector, connection: CrmConnectionRef, request: CrmVerificationRequest) -> CrmVerificationResult:
        return connector.verify_write(connection, request)
