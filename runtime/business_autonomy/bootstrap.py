from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from application.business_autonomy.adapters.ads_production_adapters import (
    GoogleAdsProductionAdapter,
    MetaAdsProductionAdapter,
    TiktokAdsProductionAdapter,
)
from application.business_autonomy.adapters.api_business_adapter import ApiBusinessChannelAdapter
from application.business_autonomy.adapters.backoffice_adapter import BackofficeChannelAdapter
from application.business_autonomy.adapters.campaign_ads_adapter import CampaignAdsChannelAdapter
from application.business_autonomy.adapters.chatbot_adapter import ChatbotChannelAdapter
from application.business_autonomy.adapters.commerce_adapter import CommerceChannelAdapter
from application.business_autonomy.adapters.commerce_production_adapters import (
    AmazonMarketplaceProductionAdapter,
    EbayMarketplaceProductionAdapter,
    EtsyMarketplaceProductionAdapter,
    OzonMarketplaceProductionAdapter,
    WildberriesMarketplaceProductionAdapter,
    WooCommerceProductionAdapter,
)
from application.business_autonomy.adapters.crm_production_adapters import (
    CallTrackingProductionAdapter,
    HubSpotProductionAdapter,
)
from application.business_autonomy.adapters.messaging_production_adapters import (
    EmailProductionAdapter,
    SmsProductionAdapter,
    WhatsAppProductionAdapter,
)
from application.business_autonomy.adapters.shopify_production_adapter import ShopifyProductionAdapter
from application.business_autonomy.adapters.telegram_production_adapter import TelegramProductionAdapter
from application.business_autonomy.adapters.website_adapter import WebsiteChannelAdapter
from application.business_autonomy.adapters.website_production_adapters import (
    WebflowProductionAdapter,
    WordpressProductionAdapter,
)
from application.business_autonomy.business_connector_framework import (
    ConnectorOnboardingService,
    StaticTrustOnboarding,
)
from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, IntegrationMode
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.guarded_service import BusinessAutonomyGuardedService
from application.business_autonomy.non_ai_onboarding_mode import NonAiOperatingMode
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.operator_admin_plane import UnifiedOperatorAdminPlane
from application.business_autonomy.persistence import (
    PersistentBusinessApprovalGate,
    PersistentBusinessAutonomyIdempotencyStore,
    PersistentBusinessOperatorOverridePolicy,
    PersistentBusinessPlanningMemorySink,
)
from application.business_autonomy.policy import BusinessAutonomyPolicy, BusinessTrustPolicy
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.registry import BusinessAdapterRegistry, RegisteredBusinessCapabilities
from application.business_autonomy.service import BusinessAutonomyService
from application.business_autonomy.trust import BusinessTrustSnapshot
from application.planning.distributed_planning_memory_backend import DistributedPlanningMemoryBackend
from execution.distributed_operator_override_backend import DistributedOperatorOverrideStore
from governance.distributed_approval_backend import DistributedApprovalStore
from reliability.distributed_idempotency_backend import DistributedIdempotencyStore
from runtime.business_autonomy.distributed_runtime_views import (
    DistributedBusinessAutonomyAudit,
    DistributedBusinessAutonomyEvidenceStore,
    DistributedBusinessPlanningMemorySink,
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
from runtime.business_autonomy.execution_support import build_execution_runtime, ensure_business_route
from runtime.business_autonomy.fleet_read_model import BusinessAutonomyFleetReadModel
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import build_default_secret_vault
from storage.distributed_evidence_audit_backend import DistributedEvidenceStore, DistributedGovernanceAuditLog


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


@dataclass
class RequestTenantCapabilityRegistryView:
    """Capability policy view bound by the canonical execution request tenant.

    BusinessAutonomyPolicy intentionally asks by business_id only. This view keeps
    tenant selection in the bootstrap/control-plane owner, not inside the policy,
    so policy remains a reader and does not become a second routing brain.
    """

    registry: DistributedBusinessRegistry
    _business_tenants: dict[str, str] = field(default_factory=dict)

    def bind(self, *, tenant_id: str, business_id: str) -> None:
        self._business_tenants[str(business_id)] = str(tenant_id)

    def register_for_tenant(self, *, tenant_id: str, business_id: str, capabilities) -> None:
        self.bind(tenant_id=tenant_id, business_id=business_id)
        record = self.registry.get(tenant_id, business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {tenant_id}:{business_id}")
        self.registry.register_or_update(
            type(record)(
                business_id=record.business_id,
                tenant_id=record.tenant_id,
                ownership_key=record.ownership_key,
                region=record.region,
                channel_kind=record.channel_kind,
                capabilities=tuple(capabilities),
                trust=record.trust,
                governance_enabled=record.governance_enabled,
                persistent_surfaces=record.persistent_surfaces,
                version=record.version,
                updated_at_utc=record.updated_at_utc,
            )
        )

    def register(self, business_id: str, capabilities) -> None:
        tenant_id = self._tenant_for_business(business_id)
        self.register_for_tenant(tenant_id=tenant_id, business_id=business_id, capabilities=capabilities)

    def get(self, business_id: str) -> RegisteredBusinessCapabilities:
        tenant_id = self._tenant_for_business(business_id)
        return self.registry.capability_snapshot(tenant_id=tenant_id, business_id=business_id)

    def supports(self, business_id: str, kind) -> bool:
        entry = self.get(business_id)
        return any(item.kind == kind and item.enabled for item in entry.capabilities)

    def snapshot(self):
        return {business_id: self.get(business_id) for business_id in sorted(self._business_tenants)}

    def _tenant_for_business(self, business_id: str) -> str:
        key = str(business_id)
        tenant_id = self._business_tenants.get(key)
        if tenant_id:
            return tenant_id
        record = self.registry.find_unique_by_business_id(key)
        if record is None:
            raise KeyError(f"business tenant binding missing: {key}")
        self.bind(tenant_id=record.tenant_id, business_id=record.business_id)
        return record.tenant_id


@dataclass
class RequestTenantTrustRegistryView:
    """Trust policy view bound by the canonical execution request tenant."""

    registry: DistributedBusinessRegistry
    _business_tenants: dict[str, str] = field(default_factory=dict)

    def bind(self, *, tenant_id: str, business_id: str) -> None:
        self._business_tenants[str(business_id)] = str(tenant_id)

    def register_for_tenant(self, *, tenant_id: str, snapshot: BusinessTrustSnapshot) -> None:
        self.bind(tenant_id=tenant_id, business_id=snapshot.business_id)
        record = self.registry.get(tenant_id, snapshot.business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {tenant_id}:{snapshot.business_id}")
        self.registry.register_or_update(
            type(record)(
                business_id=record.business_id,
                tenant_id=record.tenant_id,
                ownership_key=record.ownership_key,
                region=record.region,
                channel_kind=record.channel_kind,
                capabilities=record.capabilities,
                trust=snapshot,
                governance_enabled=record.governance_enabled,
                persistent_surfaces=record.persistent_surfaces,
                version=record.version,
                updated_at_utc=record.updated_at_utc,
            )
        )

    def register(self, snapshot: BusinessTrustSnapshot) -> None:
        tenant_id = self._tenant_for_business(snapshot.business_id)
        self.register_for_tenant(tenant_id=tenant_id, snapshot=snapshot)

    def get(self, business_id: str) -> BusinessTrustSnapshot:
        tenant_id = self._tenant_for_business(business_id)
        return self.registry.trust_snapshot(tenant_id=tenant_id, business_id=business_id)

    def _tenant_for_business(self, business_id: str) -> str:
        key = str(business_id)
        tenant_id = self._business_tenants.get(key)
        if tenant_id:
            return tenant_id
        record = self.registry.find_unique_by_business_id(key)
        if record is None:
            raise KeyError(f"business tenant binding missing: {key}")
        self.bind(tenant_id=record.tenant_id, business_id=record.business_id)
        return record.tenant_id


@dataclass(frozen=True)
class BusinessAutonomyFileSurfaceMirror:
    """Local file surface for dev/test/admin proof, fed from the canonical path."""

    root_dir: Path

    @classmethod
    def from_data_dir(cls) -> BusinessAutonomyFileSurfaceMirror:
        from os import getenv
        data_dir = Path(str(getenv('DATA_DIR', 'data') or 'data'))
        return cls(root_dir=data_dir / 'business_autonomy')

    def record_onboarding(self, *, tenant_id: str, business_id: str, capabilities, trust: BusinessTrustSnapshot) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        capability_path = self.root_dir / 'capabilities.json'
        trust_path = self.root_dir / 'trust.json'
        idempotency_path = self.root_dir / 'idempotency.json'
        key = f'{tenant_id}:{business_id}'
        capability_state = _read_json(capability_path, default={'items': {}})
        capability_state.setdefault('items', {})[key] = [
            {
                'kind': item.kind.value,
                'enabled': bool(item.enabled),
                'confidence': float(item.confidence),
                'notes': item.notes,
            }
            for item in tuple(capabilities)
        ]
        _write_json(capability_path, capability_state)
        trust_state = _read_json(trust_path, default={'items': {}})
        trust_state.setdefault('items', {})[key] = {
            'business_id': trust.business_id,
            'trust_tier': trust.trust_tier.value,
            'score': float(trust.score),
            'reasons': list(trust.reasons),
            'metadata': dict(trust.metadata or {}),
        }
        _write_json(trust_path, trust_state)
        if not idempotency_path.exists():
            _write_json(idempotency_path, {'items': {}})

    def append_result(self, result: BusinessExecutionResult):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        with (self.root_dir / 'evidence.jsonl').open('a', encoding='utf-8') as fh:
            fh.write(json.dumps({
                'execution_id': result.execution_id,
                'business_id': result.business_id,
                'goal_id': result.goal_id,
                'verdict': result.verdict.value,
                'metadata': dict(result.metadata or {}),
                'recorded_at_utc': datetime.now(UTC).isoformat(),
            }, sort_keys=True) + '\n')
        return None

    def record_execution(self, *, request, result: BusinessExecutionResult) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        tenant_id = str(request.metadata.get('tenant_id') or result.metadata.get('tenant_id') or 'global')
        recorded_at = datetime.now(UTC).isoformat()
        row = {
            'tenant_id': tenant_id,
            'business_id': request.business_id,
            'goal_id': request.goal_id,
            'goal_type': request.goal_type,
            'verdict': result.verdict.value,
            'execution_id': result.execution_id,
            'recorded_at_utc': recorded_at,
        }
        with (self.root_dir / 'planning_memory.jsonl').open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, sort_keys=True) + '\n')

        runtime_root = self.root_dir.parent / 'runtime' / 'business_autonomy'
        runtime_root.mkdir(parents=True, exist_ok=True)
        artifact = {
            **row,
            'message': result.message,
            'metrics': dict(result.metrics),
            'metadata': dict(result.metadata or {}),
            'adapter_name': result.adapter_name,
            'delegated_to_domain_engine': bool(result.delegated_to_domain_engine),
        }
        (runtime_root / f'{result.execution_id}.json').write_text(
            json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
            encoding='utf-8',
        )


@dataclass(frozen=True)
class CompositeBusinessAutonomyEvidenceStore:
    primary: DistributedBusinessAutonomyEvidenceStore
    mirror: BusinessAutonomyFileSurfaceMirror

    def append_result(self, result: BusinessExecutionResult):
        record = self.primary.append_result(result)
        self.mirror.append_result(result)
        return record

    def list_recent(self, *, tenant_id: str, limit: int = 20):
        return self.primary.list_recent(tenant_id=tenant_id, limit=limit)


@dataclass(frozen=True)
class CompositePlanningMemorySink:
    primary: HybridBusinessPlanningMemorySink
    mirror: BusinessAutonomyFileSurfaceMirror

    def record_execution(self, *, request, result: BusinessExecutionResult) -> None:
        self.primary.record_execution(request=request, result=result)
        self.mirror.record_execution(request=request, result=result)


class RequestScopedBusinessAutonomyGuardedService(BusinessAutonomyGuardedService):
    def __init__(self, *, ensure_scope, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ensure_scope = ensure_scope

    async def execute(self, request: BusinessExecutionRequest):
        self._ensure_scope(request)
        return await super().execute(request)


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
            key_prefix="__raw_scoped_key__",
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


def build_business_autonomy_guarded_service(*, business_id: str = 'external_business', seed_admin_read_model: bool = False) -> BusinessAutonomyGuardedService:
    admin_dependencies = build_business_autonomy_admin_dependencies()
    distributed = admin_dependencies['distributed']
    typed_registry = admin_dependencies['typed_registry']
    onboarding = admin_dependencies['onboarding']
    connector_secret_scope = admin_dependencies['connector_secret_scope']
    secret_vault = admin_dependencies['secret_vault']
    activation_store = admin_dependencies['activation_store']
    audit = DistributedBusinessAutonomyAudit(distributed['audit'])
    file_surface = BusinessAutonomyFileSurfaceMirror.from_data_dir()
    evidence_store = CompositeBusinessAutonomyEvidenceStore(
        primary=DistributedBusinessAutonomyEvidenceStore(distributed['evidence']),
        mirror=file_surface,
    )
    adapter_registry = BusinessAdapterRegistry()
    distributed_registry = distributed['registry']
    capability_registry = RequestTenantCapabilityRegistryView(distributed_registry)
    trust_registry = RequestTenantTrustRegistryView(distributed_registry)

    def ensure_scope_for(*, tenant_id: str, scoped_business_id: str, requested_by: str, envelope_metadata: Mapping[str, Any]) -> None:
        channel_kind, adapter_key, external_ref, region, metadata = _channel_defaults_for(scoped_business_id)
        metadata = {**metadata, **dict(envelope_metadata or {})}
        existing = distributed_registry.get(tenant_id, scoped_business_id)
        if existing is None:
            onboarding_request = BusinessOnboardingRequest(
                business_id=scoped_business_id,
                tenant_id=tenant_id,
                ownership_key=f'owner:{tenant_id}:{scoped_business_id}',
                region=region,
                channel_kind=channel_kind,
                adapter_key=adapter_key,
                external_ref=external_ref,
                requested_by=requested_by,
                metadata=metadata,
            )
            onboarding.onboard(onboarding_request)
        ensure_business_route(
            route_state=distributed['region_state'],
            tenant_id=tenant_id,
            business_id=scoped_business_id,
            primary_region=region,
            failover_region='us-east-1' if region != 'us-east-1' else 'eu-west-1',
        )
        registry_record = distributed_registry.get(tenant_id, scoped_business_id)
        assert registry_record is not None
        identity = BusinessOnboardingRequest(
            business_id=scoped_business_id,
            tenant_id=tenant_id,
            ownership_key=registry_record.ownership_key,
            region=registry_record.region,
            channel_kind=channel_kind,
            adapter_key=adapter_key,
            external_ref=external_ref,
            requested_by=requested_by,
            metadata=metadata,
        ).to_identity()
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
        try:
            adapter_registry.get(business_adapter.business_id)
        except KeyError:
            adapter_registry.register(business_adapter)
        capability_registry.register_for_tenant(
            tenant_id=tenant_id,
            business_id=business_adapter.business_id,
            capabilities=business_adapter.declared_capabilities(),
        )
        trust_snapshot = BusinessTrustSnapshot(
            business_id=business_adapter.business_id,
            trust_tier=registry_record.trust.trust_tier,
            score=registry_record.trust.score,
            reasons=registry_record.trust.reasons,
            metadata={
                **dict(registry_record.trust.metadata or {}),
                'channel_kind': registry_record.channel_kind,
                'persistent_surfaces': list(registry_record.persistent_surfaces),
                'tenant_id': tenant_id,
            },
        )
        trust_registry.register_for_tenant(tenant_id=tenant_id, snapshot=trust_snapshot)
        file_surface.record_onboarding(
            tenant_id=tenant_id,
            business_id=business_adapter.business_id,
            capabilities=business_adapter.declared_capabilities(),
            trust=trust_snapshot,
        )

    def ensure_scope(request: BusinessExecutionRequest) -> None:
        tenant_id = _tenant_id_from_request(request)
        scoped_business_id = str(request.envelope.business_id or business_id).strip() or business_id
        ensure_scope_for(
            tenant_id=tenant_id,
            scoped_business_id=scoped_business_id,
            requested_by=str(request.envelope.requested_by or 'platform'),
            envelope_metadata=dict(request.envelope.metadata or {}),
        )

    # Admin/read surfaces may ask for capability/trust before the first execution.
    # Seed is explicit so ordinary execution service construction does not pollute
    # the canonical distributed registry with tenant-demo records.
    if seed_admin_read_model:
        ensure_scope_for(
            tenant_id='tenant-demo',
            scoped_business_id=str(business_id or 'external_business'),
            requested_by='platform',
            envelope_metadata={'tenant_id': 'tenant-demo', 'admin_read_model_seed': True},
        )

    autonomy_service = BusinessAutonomyService(
        adapter_registry=adapter_registry,
        autonomy_policy=BusinessAutonomyPolicy(capability_registry),
        audit_sink=audit,
    )
    from application.business_autonomy.guards import BusinessBlastRadiusGuard, BusinessBudgetGuard

    service = RequestScopedBusinessAutonomyGuardedService(
        ensure_scope=ensure_scope,
        business_id=business_id,
        autonomy_service=autonomy_service,
        trust_policy=BusinessTrustPolicy(trust_registry),
        budget_guard=BusinessBudgetGuard(),
        blast_radius_guard=BusinessBlastRadiusGuard(),
        approval_gate=PersistentBusinessApprovalGate(store=distributed['approvals']),
        idempotency_store=PersistentBusinessAutonomyIdempotencyStore(backend=distributed['idempotency']),
        operator_override_policy=PersistentBusinessOperatorOverridePolicy(store=distributed['operator_overrides']),
        audit_sink=audit,
        evidence_store=evidence_store,
        planning_memory_sink=CompositePlanningMemorySink(
            primary=HybridBusinessPlanningMemorySink(
                distributed_sink=DistributedBusinessPlanningMemorySink(distributed['planning_memory']),
                legacy_sink=PersistentBusinessPlanningMemorySink(),
            ),
            mirror=file_surface,
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


def _tenant_id_from_request(request: BusinessExecutionRequest) -> str:
    raw = str(request.envelope.metadata.get('tenant_id') or '').strip()
    return raw or 'tenant-demo'


def _read_json(path: Path, *, default: Mapping[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return dict(raw) if isinstance(raw, Mapping) else dict(default)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
