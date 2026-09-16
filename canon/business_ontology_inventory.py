from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_BUSINESS_ONTOLOGY_INVENTORY = True


class OwnershipAuditStatus(StrEnum):
    DONE = "done"
    PARTIAL = "partial"
    DUPLICATE = "duplicate"
    LEGACY = "legacy"
    MISSING = "missing"


@dataclass(frozen=True)
class OntologyOwnershipAudit:
    entity: str
    status: OwnershipAuditStatus
    authoritative_module: str | None
    storage_owner: str | None
    allowed_writers: tuple[str, ...] = ()
    allowed_readers: tuple[str, ...] = ()
    reason: str = ""


REQUIRED_BUSINESS_ONTOLOGY = (
    "Business",
    "Organization",
    "Person",
    "Customer",
    "Lead",
    "Partner",
    "Employee",
    "Product",
    "Service",
    "Offer",
    "Channel",
    "Conversation",
    "Message",
    "Campaign",
    "Opportunity",
    "Deal",
    "Order",
    "Invoice",
    "Payment",
    "Refund",
    "Expense",
    "Revenue",
    "Asset",
    "Resource",
    "Goal",
    "Constraint",
    "Risk",
    "Hypothesis",
    "Decision",
    "Action",
    "Outcome",
    "Task",
    "Artifact",
    "Document",
    "Capability",
    "Provider",
    "Policy",
    "Evidence",
)


def _row(
    entity: str,
    status: OwnershipAuditStatus,
    owner: str | None,
    storage: str | None,
    reason: str,
    *,
    writers: tuple[str, ...] = (),
    readers: tuple[str, ...] = (),
) -> OntologyOwnershipAudit:
    return OntologyOwnershipAudit(entity, status, owner, storage, writers, readers, reason)


BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT = (
    _row(
        "Business",
        OwnershipAuditStatus.DONE,
        "contracts.business_profile",
        "application.business_autonomy.distributed_capability_trust_registry",
        "BusinessProfile is the canonical semantic projection; DistributedBusinessRegistry is the single durable tenant/business lifecycle owner and all production mutations route through its versioned register_or_update boundary.",
        writers=(
            "application.business_autonomy.business_connector_framework",
            "runtime.business_autonomy.bootstrap",
            "runtime.business_autonomy.distributed_runtime_views",
        ),
        readers=(
            "runtime.business_autonomy.fleet_read_model",
            "runtime.business_autonomy.bootstrap",
            "runtime.business_autonomy.distributed_runtime_views",
        ),
    ),
    _row(
        "Organization",
        OwnershipAuditStatus.DONE,
        "contracts.organization",
        "runtime.platform.event_store",
        "Organization is a minimal UNKNOWN-first tenant/business-scoped lifecycle. OrganizationRegistry is the single writer over canonical EventStore facts and OrganizationProjector is read-only.",
        writers=("application.organization.registry",),
        readers=("application.organization.projector",),
    ),
    _row(
        "Person",
        OwnershipAuditStatus.DONE,
        "contracts.person",
        "runtime.platform.event_store",
        "Person is a PII-minimal tenant/business-scoped human identity lifecycle. PersonRegistry is the single writer over canonical EventStore facts; behavior snapshots remain derived observations, not entity ownership.",
        writers=("application.person.registry",),
        readers=("application.person.projector",),
    ),
    _row(
        "Customer",
        OwnershipAuditStatus.DONE,
        "contracts.customer",
        "runtime.platform.event_store",
        "Canonical Customer contract uses the existing EventStore chronology; CustomerRegistry is the writer and CustomerTimelineProjector is a read projection.",
        writers=("crm.customer_registry",),
        readers=("crm.customer_timeline",),
    ),
    _row(
        "Lead",
        OwnershipAuditStatus.DONE,
        "contracts.lead",
        "runtime.platform.event_store",
        "Lead is the canonical PII-minimal tenant/business-scoped lead lifecycle. LeadRegistry is the single lifecycle writer over canonical EventStore facts; CRM/provider lead records remain transport/PII surfaces rather than ontology ownership.",
        writers=("application.lead.registry",),
        readers=("application.lead.projector",),
    ),
    _row(
        "Partner",
        OwnershipAuditStatus.DONE,
        "contracts.partner",
        "runtime.platform.event_store",
        "Partner is a PII-minimal business relationship to one canonical Person or Organization party. PartnerRegistry is the single writer over canonical EventStore facts and validates the referenced active party before creation.",
        writers=("application.partner.registry",),
        readers=("application.partner.projector",),
    ),
    _row(
        "Employee",
        OwnershipAuditStatus.DONE,
        "contracts.employee",
        "runtime.platform.event_store",
        "Employee is a PII-minimal scoped Person-to-Organization relationship. EmployeeRegistry is the single writer over canonical EventStore facts and validates both referenced lifecycle owners before creation.",
        writers=("application.employee.registry",),
        readers=("application.employee.projector",),
    ),
    _row(
        "Product",
        OwnershipAuditStatus.DONE,
        "contracts.product_contract",
        "products.product_catalog",
        "ProductContract is the single semantic owner; the immutable built-in catalog is indexed only by products/manifest.yaml and materialized exclusively by ProductLoader. Product capability flags remain distinct from runtime module wiring.",
        writers=("products.product_loader",),
        readers=("products.product_resolver", "runtime.boot.system_builder_products"),
    ),
    _row(
        "Service",
        OwnershipAuditStatus.DONE,
        "contracts.business_service",
        "runtime.platform.event_store",
        "Service is a scoped business-offering entity distinct from technical runtime/application services. BusinessServiceRegistry is the single lifecycle writer over canonical EventStore facts.",
        writers=("application.business_service.registry",),
        readers=("application.business_service.projector",),
    ),
    _row(
        "Offer",
        OwnershipAuditStatus.DONE,
        "contracts.product_contract",
        "runtime._internal.offer_catalog_mutation",
        "ProductOffer is the single canonical sellable definition. Offer is its compatibility alias; runtime OfferSummary/OfferRender/OfferEligibility are read projections, retention Offer is a legacy alias, and unused BusinessOffer/MarketplaceOffer contracts are explicitly legacy. Live tenant catalog mutations share one lock/digest/atomic-commit owner.",
        writers=(
            "runtime._internal.effects_domains.admin_pricing",
            "runtime._internal.effects_actions.offer_patch_actions",
        ),
        readers=(
            "core.offers.offer_catalog_resolver",
            "products.offer_catalog_resolver",
        ),
    ),
    _row(
        "Channel",
        OwnershipAuditStatus.DONE,
        "application.business_autonomy.channel_contracts",
        "application.business_autonomy.distributed_capability_trust_registry",
        "ChannelIdentity is the canonical semantic owner. New onboarding writes persist adapter_key/external_ref in the existing durable BusinessRegistryRecord; bootstrap reads that identity first and uses defaults only for explicit legacy rows that predate full channel identity persistence.",
        writers=("application.business_autonomy.business_connector_framework",),
        readers=("application.business_autonomy.distributed_capability_trust_registry", "runtime.business_autonomy.bootstrap"),
    ),
    _row(
        "Conversation",
        OwnershipAuditStatus.PARTIAL,
        "runtime.messaging.router_contract",
        None,
        "ConversationRoute exists but is routing projection, not full entity lifecycle.",
    ),
    _row(
        "Message",
        OwnershipAuditStatus.PARTIAL,
        "contracts.messaging_event_identity",
        None,
        "MessageIdentity is the single PII-free direction/scope identity projected by canonical inbound and outbound runtime messages. Content, delivery lifecycle, and durable universal Message storage remain scoped to existing messaging/event surfaces.",
        readers=("runtime.messaging.inbound_message", "runtime.messaging.outbound_message"),
    ),
    _row(
        "Campaign",
        OwnershipAuditStatus.DONE,
        "contracts.campaign",
        "runtime.platform.event_store",
        "Campaign is a PII-free tenant/business-scoped lifecycle entity over the existing canonical EventStore. Ads connector Campaign DTOs and campaign builders remain provider/read/plan projections rather than lifecycle ownership.",
        writers=("application.campaign.registry",),
        readers=("application.campaign.projector",),
    ),
    _row(
        "Opportunity",
        OwnershipAuditStatus.DONE,
        "contracts.opportunity",
        "runtime.platform.event_store",
        "Opportunity is a PII-free tenant/business-scoped lifecycle entity over the existing canonical EventStore. Process-discovery AutomationOpportunity and growth OpportunityScoreV1 remain detector/scoring projections rather than lifecycle ownership.",
        writers=("application.opportunity",),
        readers=("application.opportunity",),
    ),
    _row(
        "Deal",
        OwnershipAuditStatus.DONE,
        "contracts.deal",
        "runtime.platform.event_store",
        "Deal is the canonical PII-free tenant/business-scoped commercial lifecycle. DealRegistry is the single lifecycle writer over canonical EventStore facts; CRM/provider deal records remain transport surfaces rather than ontology ownership.",
        writers=("application.deal.registry",),
        readers=("application.deal.registry",),
    ),
    _row(
        "Order",
        OwnershipAuditStatus.DONE,
        "contracts.order",
        "runtime.platform.client_outcome_persistence",
        "Order is the canonical PII-free tenant/business-scoped order identity/lifecycle. OrderStore is the single writer over the canonical order namespace; the existing ClientOutcomeOrder API is a specialization/compatibility alias, and the legacy client_outcome_order namespace is read only as a fingerprinted migration source that fails closed on later divergence.",
        writers=("lead_outcomes.client_outcome_order_store",),
        readers=("lead_outcomes.client_outcome_order_store",),
    ),
    _row(
        "Invoice",
        OwnershipAuditStatus.PARTIAL,
        "billing.commercial_cycle_contract",
        None,
        "Invoice lifecycle exists in billing but is not a universal ontology owner.",
    ),
    _row(
        "Payment",
        OwnershipAuditStatus.PARTIAL,
        "core.payments.contracts",
        "runtime.platform.event_store",
        "core.payments.contracts.PaymentIdentity and PaymentLifecycleStatus are the canonical PII-free payment identity/lifecycle vocabulary over existing payment EventStore chronology. Finance records, provider checkout/status values, billing collection results, and the payment outbox remain scoped projections/transport state. Payment remains PARTIAL because historical payment events do not uniformly carry universal business_id scope or a complete ontology lifecycle projection.",
        writers=(
            "runtime._internal.effects_actions.payments.selection",
            "runtime._internal.effects_actions.payments.reconciliation",
        ),
        readers=("core.payments.read_model",),
    ),
    _row(
        "Refund",
        OwnershipAuditStatus.DONE,
        "billing.recovery_contracts",
        "runtime.platform.billing_recovery_store",
        "RefundResult is the single canonical refund entity contract; RefundOrchestrator is the only domain lifecycle writer and the platform SQLite recovery store is the durable schema-versioned storage owner. In-memory storage remains a test/default adapter, not an alternative durable owner.",
        writers=("billing.refund_orchestrator",),
        readers=("billing.recovery_store",),
    ),
    _row(
        "Expense",
        OwnershipAuditStatus.PARTIAL,
        "core.finance.types",
        None,
        "Finance type exists without complete ontology ownership contract.",
    ),
    _row(
        "Revenue",
        OwnershipAuditStatus.PARTIAL,
        "core.economics.types",
        None,
        "core.economics.types.RevenueSignal is the canonical normalized economics read signal after removing the unused contracts.revenue_signal duplicate. Finance records, monetization snapshots, billing facts, and analytics reports remain scoped projections; universal tenant/business-scoped Revenue lifecycle/storage ownership is still incomplete.",
        readers=("core.economics.service",),
    ),
    _row(
        "Asset",
        OwnershipAuditStatus.DONE,
        "contracts.asset",
        "runtime.platform.event_store",
        "Asset is the canonical PII-free tenant/business-scoped business-asset lifecycle. AssetRegistry is the single lifecycle writer over canonical EventStore facts; technical resource identifiers and provider resources remain non-ontology projections.",
        writers=("application.asset",),
        readers=("application.asset",),
    ),
    _row(
        "Resource",
        OwnershipAuditStatus.DONE,
        "contracts.business_resource",
        "runtime.platform.event_store",
        "BusinessResource is the canonical PII-free operational Resource identity/lifecycle. BusinessResourceRegistry is the single EventStore writer; technical ResourceAllocator/provider resource_id surfaces remain infrastructure or transport metadata, not ontology ownership.",
        writers=("application.business_resource",),
        readers=("application.business_resource",),
    ),
    _row(
        "Goal",
        OwnershipAuditStatus.DONE,
        "contracts.business_goal",
        "runtime.platform.event_store",
        "BusinessGoal is the canonical PII-free hierarchical Goal identity/lifecycle. BusinessGoalRegistry is the single EventStore writer; planners, execution goal envelopes, scores and growth goals are projections or domain-specific inputs rather than competing lifecycle owners.",
        writers=("application.business_goal",),
        readers=("application.business_goal",),
    ),
    _row(
        "Constraint",
        OwnershipAuditStatus.DONE,
        "contracts.business_constraints",
        "runtime.platform.event_store",
        "BusinessConstraint is the canonical PII-free Constraint identity/lifecycle with immutable subject relation and canonical hard/soft severity. BusinessConstraintRegistry is the single EventStore writer; execution PolicyConstraint and domain-specific constraint objects consume or project this vocabulary.",
        writers=("application.business_constraint",),
        readers=("application.business_constraint",),
    ),
    _row(
        "Risk",
        OwnershipAuditStatus.PARTIAL,
        "contracts.risk",
        None,
        "contracts.risk.RiskLevel is the single generic risk-severity vocabulary reused by experiments, human governance, and runtime safety compatibility surfaces. Numeric safety scores, economic risks, and domain-specific risk states remain scoped projections; universal tenant/business-scoped Risk identity/lifecycle/storage ownership is still incomplete.",
        readers=("core.experiments.enums", "core.human_governance.enums", "runtime.platform.support.safety"),
    ),
    _row(
        "Hypothesis",
        OwnershipAuditStatus.DONE,
        "contracts.growth_hypothesis",
        "core.growth.strategy.backlog_store",
        "GrowthHypothesisV1 is the single semantic owner; core.growth.strategy.contracts only re-exports it, while backlog_store is the sole EventStore chronology owner for creation/state reads and writes.",
        writers=("core.growth.strategy.backlog_store",),
        readers=("core.growth.strategy.backlog_store",),
    ),
    _row(
        "Decision",
        OwnershipAuditStatus.DONE,
        "contracts.decisioning.sovereign_decision_contract",
        "core.ai.decision_archive",
        "The sovereign Decision contract has one issuer path; application.decision_runtime.emission is the canonical runtime archive writer, DecisionArchive is the storage abstraction, and replay/recovery are read-only consumers. The canonical e2e smoke is a verification-only direct archive client, not an alternative runtime owner.",
        writers=("application.decision_runtime.emission",),
        readers=("runtime.replay", "runtime.recovery"),
    ),
    _row(
        "Action",
        OwnershipAuditStatus.PARTIAL,
        "contracts.action_intent",
        "storage.evidence_store",
        "ActionIntentV1 is the canonical non-effectful AI-to-execution semantic owner. New closed-loop intents are preserved as full immutable bodies inside the existing canonical EvidenceStore and projected read-only; legacy Evidence rows created before full-body intent persistence require historical backfill before Action can be marked DONE.",
        writers=("application.evidence.evidence_persistence",),
        readers=("application.action.evidence_projection",),
    ),
    _row(
        "Outcome",
        OwnershipAuditStatus.PARTIAL,
        "contracts.business_outcome",
        "storage.evidence_store",
        "BusinessOutcomeV1 is the canonical semantic owner. New closed-loop outcomes are persisted inside the existing canonical EvidenceStore and projected read-only by BusinessOutcomeEvidenceProjector; legacy Evidence rows created before full-body persistence still require historical backfill before Outcome can be marked DONE.",
        writers=("application.evidence.evidence_persistence",),
        readers=("application.outcome.evidence_projection",),
    ),
    _row(
        "Task",
        OwnershipAuditStatus.DONE,
        "contracts.task",
        "runtime.platform.event_store",
        "DurableTask is the canonical task entity/state machine; DurableTaskRegistry is the single lifecycle writer over canonical EventStore facts and DurableTaskProjector is read-only. Full Run/Step/Checkpoint/Wait/Compensation runtime remains a separate Phase 9 gap.",
        writers=("application.task.registry",),
        readers=("application.task.projector",),
    ),
    _row(
        "Artifact",
        OwnershipAuditStatus.DONE,
        "contracts.artifact",
        "runtime.platform.event_store",
        "Artifact is the canonical immutable business-artifact metadata identity; ArtifactRegistry owns lifecycle facts in the existing EventStore while binary/blob storage remains external and non-authoritative for ontology ownership.",
        writers=("application.artifact.registry",),
        readers=("application.artifact.projector",),
    ),
    _row(
        "Document",
        OwnershipAuditStatus.DONE,
        "contracts.document",
        "runtime.platform.event_store",
        "Document is the canonical stable business-document identity; revisions point to immutable canonical Artifacts while DocumentRegistry owns document lifecycle facts in the existing EventStore.",
        writers=("application.document.registry",),
        readers=("application.document.projector",),
    ),
    _row(
        "Capability",
        OwnershipAuditStatus.PARTIAL,
        "application.business_autonomy.integration_capability_catalog",
        None,
        "Business integration capability definitions have one semantic catalog after removing duplicate DecisionCore advisory vocabularies. Decision advisory capabilities and execution-route capabilities remain intentionally scoped projections; universal capability lifecycle/storage ownership is still incomplete.",
    ),
    _row(
        "Provider",
        OwnershipAuditStatus.DONE,
        "application.business_autonomy.provider_catalog",
        "runtime.business_autonomy.provider_activation_store",
        "ProviderDefinition catalog is the single static semantic owner and FileProviderActivationStore is the single durable tenant/business/provider activation lifecycle owner; ProviderAdminService is the only production mutation boundary.",
        writers=("application.business_autonomy.provider_admin_service",),
        readers=("application.business_autonomy.provider_admin_service",),
    ),
    _row(
        "Policy",
        OwnershipAuditStatus.PARTIAL,
        "core.ai.policy_registry",
        None,
        "PolicyDecisionV1 remains the canonical policy verdict contract, while core.ai.policy_registry is the single production runtime Policy entity/version lifecycle owner. Registered policy ids carry their real @vN identity through active/canary/promotion/rollback snapshots; Policy remains PARTIAL until arbitrary runtime deployment state has one durable restart/replay owner.",
        writers=("core.ai.policy_registry",),
        readers=("core.policies.selector",),
    ),
    _row(
        "Evidence",
        OwnershipAuditStatus.DONE,
        "storage.evidence_store",
        "storage.evidence_store",
        "Canonical EvidenceRecord/storage ownership is locked; active durable writers route to it, legacy surfaces are migration/archive or mirror-only, historical backfills are idempotent/fail-closed, and closed-loop lineage preserves all six canonical stages.",
        writers=(
            "application.business_autonomy.evidence_projection",
            "application.evidence.evidence_persistence",
            "application.evidence.market_intelligence_evidence",
            "application.process_discovery.canonical_adapters",
            "runtime.business_autonomy.provider_runtime_audit",
            "runtime.monetization.revenue_advisory_store",
        ),
        readers=("storage.distributed_evidence_audit_backend", "application.business_autonomy.persistence"),
    ),
)


def ontology_ownership_by_entity() -> dict[str, OntologyOwnershipAudit]:
    return {row.entity: row for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT}


__all__ = [
    "BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT",
    "CANON_BUSINESS_ONTOLOGY_INVENTORY",
    "OntologyOwnershipAudit",
    "OwnershipAuditStatus",
    "REQUIRED_BUSINESS_ONTOLOGY",
    "ontology_ownership_by_entity",
]
