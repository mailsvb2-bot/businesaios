from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from collections.abc import Mapping, Sequence

from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind
from application.business_autonomy.contracts import BusinessCapability, CapabilityKind
from application.business_autonomy.distributed_capability_trust_registry import (
    BusinessRegistryRecord,
    DistributedBusinessRegistry,
)
from application.business_autonomy.non_ai_onboarding_mode import NonAiModeResolver
from application.business_autonomy.onboarding_contract import (
    BusinessOnboardingRequest,
    BusinessOnboardingResult,
    BusinessOnboardingState,
    OnboardingStage,
)
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier

CANON_BUSINESS_CONNECTOR_FRAMEWORK = True


class TrustOnboardingPort(Protocol):
    def evaluate(self, *, business_id: str, tenant_id: str, channel_kind: str, metadata: Mapping[str, Any]) -> BusinessTrustSnapshot: ...


class GovernanceEnablementPort(Protocol):
    def enable(self, *, tenant_id: str, business_id: str, ownership_key: str, non_ai_mode: Mapping[str, object]) -> tuple[str, ...]: ...


class PersistenceSurfacePort(Protocol):
    def enable_surfaces(self, *, tenant_id: str, business_id: str, region: str) -> tuple[str, ...]: ...


class CapabilitySemanticsMapper:
    _ACTION_MAP = {
        "message_send": CapabilityKind.CONTENT_ENGINE,
        "message_read": CapabilityKind.ANALYTICS_ENGINE,
        "content_publish": CapabilityKind.CONTENT_ENGINE,
        "content_update": CapabilityKind.CONTENT_ENGINE,
        "web_analytics_pull": CapabilityKind.ANALYTICS_ENGINE,
        "api_call": CapabilityKind.DOMAIN_AI,
        "api_read": CapabilityKind.ANALYTICS_ENGINE,
        "catalog_sync": CapabilityKind.CONTENT_ENGINE,
        "order_sync": CapabilityKind.PAYMENT_ORCHESTRATOR,
        "refund_request": CapabilityKind.PAYMENT_ORCHESTRATOR,
        "task_create": CapabilityKind.DOMAIN_SCHEDULER,
        "task_assign": CapabilityKind.DOMAIN_SCHEDULER,
        "report_read": CapabilityKind.ANALYTICS_ENGINE,
        "campaign_launch": CapabilityKind.PRICING_ENGINE,
        "campaign_metrics_pull": CapabilityKind.ANALYTICS_ENGINE,
    }

    _CHANNEL_DEFAULTS = {
        ChannelKind.CHATBOT: (CapabilityKind.CONTENT_ENGINE,),
        ChannelKind.WEBSITE: (CapabilityKind.CONTENT_ENGINE, CapabilityKind.ANALYTICS_ENGINE),
        ChannelKind.API_BUSINESS: (CapabilityKind.DOMAIN_AI,),
        ChannelKind.COMMERCE: (CapabilityKind.PAYMENT_ORCHESTRATOR, CapabilityKind.CONTENT_ENGINE),
        ChannelKind.BACKOFFICE: (CapabilityKind.DOMAIN_SCHEDULER,),
        ChannelKind.CAMPAIGN_ADS: (CapabilityKind.PRICING_ENGINE, CapabilityKind.ANALYTICS_ENGINE),
    }

    def map_capabilities(
        self,
        *,
        channel_kind: ChannelKind,
        descriptors: Sequence[ChannelCapabilityDescriptor],
    ) -> tuple[BusinessCapability, ...]:
        resolved: dict[CapabilityKind, BusinessCapability] = {}
        for kind in self._CHANNEL_DEFAULTS.get(channel_kind, ()):
            resolved[kind] = BusinessCapability(kind=kind, enabled=True, confidence=0.55, notes=f"channel_default:{channel_kind.value}")
        for descriptor in descriptors:
            descriptor.validate()
            kinds = {self._ACTION_MAP.get(action) for action in descriptor.action_types}
            kinds.discard(None)
            for kind in kinds:
                assert kind is not None
                confidence = 0.9 if descriptor.write_enabled else 0.75
                current = resolved.get(kind)
                if current is None or current.confidence < confidence:
                    resolved[kind] = BusinessCapability(
                        kind=kind,
                        enabled=True,
                        confidence=confidence,
                        notes=descriptor.capability_key,
                    )
        return tuple(sorted(resolved.values(), key=lambda item: item.kind.value))


@dataclass(frozen=True)
class ConnectorOnboardingService:
    adapter_registry: TypedChannelAdapterRegistry
    business_registry: DistributedBusinessRegistry
    trust_onboarding: TrustOnboardingPort
    governance_enablement: GovernanceEnablementPort
    persistence_surface: PersistenceSurfacePort
    capability_mapper: CapabilitySemanticsMapper = CapabilitySemanticsMapper()
    non_ai_mode_resolver: NonAiModeResolver = NonAiModeResolver()

    def onboard(self, request: BusinessOnboardingRequest) -> BusinessOnboardingResult:
        request.validate()
        identity = request.to_identity()
        resolved = self.adapter_registry.resolve(identity)
        discovered = tuple(resolved.adapter.discover_capabilities(identity=identity))
        mapped_capabilities = self.capability_mapper.map_capabilities(
            channel_kind=request.channel_kind,
            descriptors=discovered,
        )
        mode_policy = self.non_ai_mode_resolver.resolve(metadata=request.metadata)
        trust = self.trust_onboarding.evaluate(
            business_id=request.business_id,
            tenant_id=request.tenant_id,
            channel_kind=request.channel_kind.value,
            metadata=request.metadata,
        )
        governance_surfaces = self.governance_enablement.enable(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            ownership_key=request.ownership_key,
            non_ai_mode=mode_policy.to_metadata(),
        )
        persistent_surfaces = self.persistence_surface.enable_surfaces(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            region=request.region,
        )
        record = BusinessRegistryRecord(
            business_id=request.business_id,
            tenant_id=request.tenant_id,
            ownership_key=request.ownership_key,
            region=request.region,
            channel_kind=request.channel_kind.value,
            capabilities=mapped_capabilities,
            trust=trust,
            governance_enabled=True,
            persistent_surfaces=tuple(sorted(set(governance_surfaces + persistent_surfaces))),
        )
        self.business_registry.register_or_update(record)
        states = (
            BusinessOnboardingState(OnboardingStage.REGISTERED, request.business_id, request.tenant_id, {"channel_kind": request.channel_kind.value}),
            BusinessOnboardingState(OnboardingStage.CAPABILITY_DISCOVERED, request.business_id, request.tenant_id, {"capability_count": len(mapped_capabilities), "adapter_key": request.adapter_key}),
            BusinessOnboardingState(OnboardingStage.TRUST_ONBOARDED, request.business_id, request.tenant_id, {"trust_tier": trust.trust_tier.value, "score": trust.score}),
            BusinessOnboardingState(OnboardingStage.MODE_RESOLVED, request.business_id, request.tenant_id, mode_policy.to_metadata()),
            BusinessOnboardingState(OnboardingStage.OWNERSHIP_BOUND, request.business_id, request.tenant_id, {"ownership_key": request.ownership_key, "region": request.region}),
            BusinessOnboardingState(OnboardingStage.GOVERNANCE_ENABLED, request.business_id, request.tenant_id, {"surfaces": list(governance_surfaces)}),
            BusinessOnboardingState(OnboardingStage.PERSISTENCE_ENABLED, request.business_id, request.tenant_id, {"surfaces": list(persistent_surfaces)}),
            BusinessOnboardingState(OnboardingStage.READY, request.business_id, request.tenant_id, {"adapter_key": request.adapter_key}),
        )
        return BusinessOnboardingResult(
            business_id=request.business_id,
            tenant_id=request.tenant_id,
            states=states,
            ready=True,
            persistent_surfaces=tuple(sorted(set(governance_surfaces + persistent_surfaces))),
        )


class StaticTrustOnboarding:
    def evaluate(self, *, business_id: str, tenant_id: str, channel_kind: str, metadata: Mapping[str, Any]) -> BusinessTrustSnapshot:
        score = 0.85 if bool(metadata.get("verified_owner")) else 0.45
        tier = BusinessTrustTier.HIGH if score >= 0.8 else BusinessTrustTier.MEDIUM
        reasons = (
            "verified_owner" if bool(metadata.get("verified_owner")) else "owner_not_verified",
            f"channel_kind:{channel_kind}",
        )
        return BusinessTrustSnapshot(
            business_id=business_id,
            trust_tier=tier,
            score=score,
            reasons=reasons,
            metadata={"tenant_id": tenant_id},
        )


__all__ = [
    "CANON_BUSINESS_CONNECTOR_FRAMEWORK",
    "CapabilitySemanticsMapper",
    "ConnectorOnboardingService",
    "GovernanceEnablementPort",
    "PersistenceSurfacePort",
    "StaticTrustOnboarding",
    "TrustOnboardingPort",
]
