from __future__ import annotations

from crm.crm_verification_contract import CrmVerificationRequest
from crm.verification.crm_write_verifier import CrmWriteVerifier


class CrmStageVerifier(CrmWriteVerifier):
    def build_request(self, *, provider_key: str, record_id: str | None, expected_fields: dict[str, object] | None = None) -> CrmVerificationRequest:
        return CrmVerificationRequest(entity_type='stage', provider_key=provider_key, record_id=record_id, expected_fields=expected_fields or {})
