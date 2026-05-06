from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from application.business_autonomy.adapters.api_business_adapter import ApiBusinessChannelAdapter
from application.business_autonomy.adapters.backoffice_adapter import BackofficeChannelAdapter
from application.business_autonomy.adapters.campaign_ads_adapter import CampaignAdsChannelAdapter
from application.business_autonomy.adapters.chatbot_adapter import ChatbotChannelAdapter
from application.business_autonomy.adapters.commerce_adapter import CommerceChannelAdapter
from application.business_autonomy.adapters.website_adapter import WebsiteChannelAdapter
from application.business_autonomy.adapters.shopify_production_adapter import ShopifyProductionAdapter
from application.business_autonomy.adapters.telegram_production_adapter import TelegramProductionAdapter
from application.business_autonomy.adapters.ads_production_adapters import GoogleAdsProductionAdapter, MetaAdsProductionAdapter, TiktokAdsProductionAdapter
from application.business_autonomy.adapters.commerce_production_adapters import AmazonMarketplaceProductionAdapter, EbayMarketplaceProductionAdapter, EtsyMarketplaceProductionAdapter, OzonMarketplaceProductionAdapter, WildberriesMarketplaceProductionAdapter, WooCommerceProductionAdapter
from application.business_autonomy.adapters.crm_production_adapters import CallTrackingProductionAdapter, HubSpotProductionAdapter
from application.business_autonomy.adapters.messaging_production_adapters import EmailProductionAdapter, SmsProductionAdapter, WhatsAppProductionAdapter
from application.business_autonomy.adapters.website_production_adapters import WebflowProductionAdapter, WordpressProductionAdapter
from application.business_autonomy.business_connector_framework import (
    ConnectorOnboardingService,
    StaticTrustOnboarding,
)
from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.contracts import IntegrationMode
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.guarded_service import BusinessAutonomyGuardedService
from application.business_autonomy.non_ai_onboarding_mode import NonAiOperatingMode
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.operator_admin_plane import UnifiedOperatorAdminPlane
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.persistence import (
    PersistentBusinessApprovalGate,
    PersistentBusinessAutonomyIdempotencyStore,
    PersistentBusinessOperatorOverridePolicy,
    PersistentBusinessPlanningMemorySink,
)
from application.business_autonomy.policy import BusinessAutonomyPolicy, BusinessTrustPolicy
from application.business_autonomy.registry import BusinessAdapterRegistry
from application.business_autonomy.service import BusinessAutonomyService
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from runtime.business_autonomy.fleet_read_model import BusinessAutonomyFleetReadModel
from runtime.business_autonomy.distributed_runtime_views import (
    DistributedBusinessAutonomyAudit,
    DistributedBusinessAutonomyEvidenceStore,
    DistributedBusinessPlanningMemorySink,
    DistributedCapabilityRegistryView,
    DistributedTrustRegistryView,
    HybridBusinessPlanningMemorySink,
)
from runtime.business_autonomy.distributed_state import (
    FileApprovalDocumentPort,
    FileDistributedCompareAndSwap,
    FileDistributedDocumentStore,
    FileDistributedEvidenceAppendPort,
    FileDistributedSequenceStore,
    FileOperatorOverrideDocumentPort,
    FilePlanningMemoryDocumentPort,
    FileRegionRouteState,
)
from governance.distributed_approval_backend import DistributedApprovalStore
from execution.distributed_operator_override_backend import DistributedOperatorOverrideStore
from reliability.distributed_idempotency_backend import DistributedIdempotencyStore
from storage.distributed_evidence_audit_backend import DistributedEvidenceStore, DistributedGovernanceAuditLog
from application.planning.distributed_planning_memory_backend import DistributedPlanningMemoryBackend
from runtime.business_autonomy.execution_support import build_execution_runtime, ensure_business_route
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import build_default_secret_vault


@dataclass(frozen=True)
class StaticGovernanceEnablement:
    def enable(self, *, tenant_id: str, business_id: str, ownership_key: str, non_ai_mode: Mapping[str, object]) -> tuple[str, ...]:
        surfaces = ['approval', 'operator_override', 'audit']
        if bool(non_ai_mode.get('requires_human_approval', False)):
            surfaces.append('supervision')
        return tuple(sorted(set(surfaces)))


@dataclass(frozen=True)
class StaticPersistenceSurface:
    def enable_surfaces(self, *, tenant_id: str, business_id: str, region: str) -> tuple[str, ...]:
        return ('evidence', 'idempotency', 'planning_memory', f'region:{region}')


def _business_autonomy_state_root() -> str:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return str(business_autonomy_runtime_dir() / "distributed")


def _build_distributed_state() -> dict[str, object]:
    root = _business_autonomy_state_root()
    documents = FileDistributedDocumentStore(root_dir=f"{root}/documents")
    evidence_port = FileDistributedEvidenceAppendPort(root_dir=f"{root}/append")
    return {
        "documents": documents,
        "approvals": DistributedApprovalStore(FileApprovalDocumentPort(documents)),
        "operator_overrides": DistributedOperatorOverrideStore(FileOperatorOverrideDocumentPort(documents)),
        "idempotency": DistributedIdempotencyStore(
            cas=FileDistributedCompareAndSwap(documents, collection="idempotency_records"),
            sequence=FileDistributedSequenceStore(f"{root}/sequences.json"),
            key_prefix="business_autonomy/idempotency",
        ),
        "audit": DistributedGovernanceAuditLog(evidence_port, partition_prefix="business_autonomy_audit"),
        "evidence": DistributedEvidenceStore(evidence_port),
        "planning_memory": DistributedPlanningMemoryBackend(FilePlanningMemoryDocumentPort(documents)),
        "registry": DistributedBusinessRegistry(documents=documents),
        "region_state": FileRegionRouteState(documents),
    }


def _channel_defaults_for(business_id: str) -> tuple[ChannelKind, str, str, str, dict[str, Any]]:
    normalized = str(business_id).strip().lower()
    if 'site' in normalized or 'web' in normalized:
        return ChannelKind.WEBSITE, 'website.default', f'https://{normalized}.example.com', 'eu-west-1', {
            'non_ai_mode': NonAiOperatingMode.SUPERVISED.value,
            'verified_owner': True,
            'action_type': 'profile_publish',
            'autonomy_tier': 'supervised',
        }
    if 'shop' in normalized or 'commerce' in normalized:
        return ChannelKind.COMMERCE, 'commerce.default', f'commerce://{normalized}', 'eu-west-1', {
            'non_ai_mode': NonAiOperatingMode.POLICY_GUIDED.value,
            'verified_owner': True,
            'action_type': 'platform_listing_write',
            'autonomy_tier': 'bounded_autonomy',
        }
    if 'bot' in normalized:
        return ChannelKind.CHATBOT, 'chatbot.default', f'bot://{normalized}', 'eu-west-1', {
            'verified_owner': True,
            'action_type': 'communications_write',
            'autonomy_tier': 'bounded_autonomy',
        }
    return ChannelKind.API_BUSINESS, 'api.default', f'api://{normalized}', 'eu-west-1', {
        'verified_owner': True,
        'action_type': 'internal_execution',
        'autonomy_tier': 'bounded_autonomy',
    }


def build_business_autonomy_admin_dependencies() -> dict[str, object]:
    distributed = _build_distributed_state()
    typed_registry = _build_typed_channel_registry()
    onboarding = ConnectorOnboardingService(
        adapter_registry=typed_registry,
        business_registry=distributed['registry'],
        trust_onboarding=StaticTrustOnboarding(),
        governance_enablement=StaticGovernanceEnablement(),
        persistence_surface=StaticPersistenceSurface(),
    )
    return {
        'distributed': distributed,
        'typed_registry': typed_registry,
        'onboarding': onboarding,
        'connector_secret_scope': ConnectorSecretScope(),
        'secret_vault': build_default_secret_vault(),
        'activation_store': FileProviderActivationStore(distributed['documents']),
    }


def _build_typed_channel_registry() -> TypedChannelAdapterRegistry:
    registry = TypedChannelAdapterRegistry()
    for adapter in (
        ChatbotChannelAdapter(),
        TelegramProductionAdapter(),
        WhatsAppProductionAdapter(),
        EmailProductionAdapter(),
        SmsProductionAdapter(),
        WebsiteChannelAdapter(),
        WebflowProductionAdapter(),
        WordpressProductionAdapter(),
        ApiBusinessChannelAdapter(),
        CommerceChannelAdapter(),
        ShopifyProductionAdapter(),
        WooCommerceProductionAdapter(),
        AmazonMarketplaceProductionAdapter(),
        EbayMarketplaceProductionAdapter(),
        EtsyMarketplaceProductionAdapter(),
        WildberriesMarketplaceProductionAdapter(),
        OzonMarketplaceProductionAdapter(),
        BackofficeChannelAdapter(),
        CallTrackingProductionAdapter(),
        HubSpotProductionAdapter(),
        CampaignAdsChannelAdapter(),
        MetaAdsProductionAdapter(),
        GoogleAdsProductionAdapter(),
        TiktokAdsProductionAdapter(),
    ):
        registry.register(adapter)
    return registry


def build_business_autonomy_guarded_service(*, business_id: str = 'external_business') -> BusinessAutonomyGuardedService:
    admin_dependencies = build_business_autonomy_admin_dependencies()
    distributed = admin_dependencies['distributed']
    typed_registry = admin_dependencies['typed_registry']
    onboarding = admin_dependencies['onboarding']
    connector_secret_scope = admin_dependencies['connector_secret_scope']
    secret_vault = admin_dependencies['secret_vault']
    activation_store = admin_dependencies['activation_store']
    audit = DistributedBusinessAutonomyAudit(distributed['audit'])
    evidence_store = DistributedBusinessAutonomyEvidenceStore(distributed['evidence'])
    adapter_registry = BusinessAdapterRegistry()

    channel_kind, adapter_key, external_ref, region, metadata = _channel_defaults_for(business_id)
    distributed_registry = distributed['registry']
    onboarding_request = BusinessOnboardingRequest(
        business_id=business_id,
        tenant_id='tenant-demo',
        ownership_key=f'owner:{business_id}',
        region=region,
        channel_kind=channel_kind,
        adapter_key=adapter_key,
        external_ref=external_ref,
        requested_by='platform',
        metadata=metadata,
    )
    onboarding.onboard(onboarding_request)
    ensure_business_route(
        route_state=distributed['region_state'],
        tenant_id='tenant-demo',
        business_id=business_id,
        primary_region=region,
        failover_region='us-east-1' if region != 'us-east-1' else 'eu-west-1',
    )
    registry_record = distributed_registry.get('tenant-demo', business_id)
    assert registry_record is not None
    identity = onboarding_request.to_identity()
    resolved = typed_registry.resolve(identity)
    business_adapter = ChannelBackedBusinessAdapter(
        identity=identity,
        channel_adapter=resolved.adapter,
        capabilities=tuple(registry_record.capabilities),
        modes=(
            IntegrationMode.OBSERVE_ONLY,
            IntegrationMode.POLICY_GUARDED_DELEGATED,
            IntegrationMode.SUPERVISED,
            IntegrationMode.LOW_AUTONOMY,
            IntegrationMode.PLATFORM_DIRECT,
        ),
    )
    adapter_registry.register(business_adapter)
    capability_registry = DistributedCapabilityRegistryView(distributed_registry, tenant_id='tenant-demo')
    trust_registry = DistributedTrustRegistryView(distributed_registry, tenant_id='tenant-demo')
    capability_registry.register(business_id=business_adapter.business_id, capabilities=business_adapter.declared_capabilities())
    trust_registry.register(
        BusinessTrustSnapshot(
            business_id=business_adapter.business_id,
            trust_tier=registry_record.trust.trust_tier,
            score=registry_record.trust.score,
            reasons=registry_record.trust.reasons,
            metadata={
                **dict(registry_record.trust.metadata or {}),
                'channel_kind': registry_record.channel_kind,
                'persistent_surfaces': list(registry_record.persistent_surfaces),
            },
        )
    )

    autonomy_service = BusinessAutonomyService(
        adapter_registry=adapter_registry,
        autonomy_policy=BusinessAutonomyPolicy(capability_registry),
        audit_sink=audit,
    )
    from application.business_autonomy.guards import BusinessBlastRadiusGuard, BusinessBudgetGuard

    service = BusinessAutonomyGuardedService(
        autonomy_service=autonomy_service,
        trust_policy=BusinessTrustPolicy(trust_registry),
        budget_guard=BusinessBudgetGuard(),
        blast_radius_guard=BusinessBlastRadiusGuard(),
        approval_gate=PersistentBusinessApprovalGate(store=distributed['approvals']),
        idempotency_store=PersistentBusinessAutonomyIdempotencyStore(backend=distributed['idempotency']),
        operator_override_policy=PersistentBusinessOperatorOverridePolicy(store=distributed['operator_overrides']),
        audit_sink=audit,
        evidence_store=evidence_store,
        planning_memory_sink=HybridBusinessPlanningMemorySink(
            distributed_sink=DistributedBusinessPlanningMemorySink(distributed['planning_memory']),
            legacy_sink=PersistentBusinessPlanningMemorySink(),
        ),
    )
    service._distributed_business_registry = distributed_registry
    service._typed_channel_registry = typed_registry
    service._operator_admin_plane = UnifiedOperatorAdminPlane(BusinessAutonomyFleetReadModel(distributed_registry))
    service._execution_runtime = build_execution_runtime(route_state=distributed['region_state'])
    service._provider_admin_service = ProviderAdminService(
        onboarding_service=onboarding,
        secret_vault=secret_vault,
        connector_secret_scope=connector_secret_scope,
        activation_store=activation_store,
        route_state=distributed['region_state'],
    )
    return service
