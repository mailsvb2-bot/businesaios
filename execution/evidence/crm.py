from __future__ import annotations

from dataclasses import dataclass

from crm.verification.crm_write_verifier import CrmWriteVerifier
from execution.evidence.base import EvidenceVerifier
from execution.evidence.result import EvidenceResult


@dataclass(frozen=True)
class CrmEvidenceVerifier(EvidenceVerifier):
    """Compatibility verifier that preserves the project's evidence router contract.

    The canonical CRM write verification logic lives in ``crm.verification``.
    This shim keeps the existing ``execution.evidence`` surface intact so the
    patchset does not break current imports or execution routing.
    """

    action_prefixes: tuple[str, ...] = ("ACTION_CRM_", "route_lead", "crm_")

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status="crm",
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


__all__ = ["CrmEvidenceVerifier", "CrmWriteVerifier"]
