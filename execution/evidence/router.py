from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crm.verification.crm_write_verifier import CrmWriteVerifier
from execution.evidence.base import EvidenceVerifier
from execution.evidence.market_intelligence import MarketIntelligenceEvidenceVerifier
from execution.evidence.result import EvidenceResult


CANON_EVIDENCE_ROUTER = True


@dataclass(frozen=True)
class AdsEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = ('ACTION_ADS_', 'ACTION_LAUNCH_', 'launch_campaign', 'update_budget')

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status='ads',
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


@dataclass(frozen=True)
class CommunicationsEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = ('ACTION_COMM_', 'send_', 'message_')

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status='communications',
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


@dataclass(frozen=True)
class CrmEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = ('ACTION_CRM_', 'route_lead', 'crm_')

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status='crm',
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


@dataclass(frozen=True)
class PlatformsEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = ('ACTION_PLATFORM_', 'create_listing', 'reply_to_inquiry', 'request_review')

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status='platforms',
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


@dataclass(frozen=True)
class SeoEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = ('ACTION_SEO_', 'create_landing_page', 'publish_service_page')

    def verify(self, request, action, action_result, connector_result) -> EvidenceResult:
        return self._verify_from_payload(
            status='seo',
            request=request,
            action=action,
            action_result=action_result,
            connector_result=connector_result,
        )


@dataclass(frozen=True)
class EvidenceRouter:
    verifiers: tuple[EvidenceVerifier, ...] = field(default_factory=tuple)

    def verify(self, *, request: Any, action: Any, action_result: Any, connector_result: Any | None = None) -> EvidenceResult:
        action_type = str(getattr(action, "action_type", "") or "")
        for verifier in self.verifiers:
            if not verifier.action_prefixes:
                continue
            if any(token and token in action_type for token in verifier.action_prefixes):
                return verifier.verify(request, action, action_result, connector_result)
        return PlatformsEvidenceVerifier().verify(request, action, action_result, connector_result)


def build_evidence_router() -> EvidenceRouter:
    return EvidenceRouter(
        verifiers=(
            AdsEvidenceVerifier(),
            PlatformsEvidenceVerifier(),
            SeoEvidenceVerifier(),
            CommunicationsEvidenceVerifier(),
            CrmEvidenceVerifier(),
            MarketIntelligenceEvidenceVerifier(),
        )
    )


__all__ = [
    'CANON_EVIDENCE_ROUTER',
    'EvidenceRouter',
    'build_evidence_router',
    'AdsEvidenceVerifier',
    'PlatformsEvidenceVerifier',
    'SeoEvidenceVerifier',
    'CommunicationsEvidenceVerifier',
    'CrmEvidenceVerifier',
    'CrmWriteVerifier',
    'MarketIntelligenceEvidenceVerifier',
]
