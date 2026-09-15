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
        OwnershipAuditStatus.PARTIAL,
        "contracts.lead",
        None,
        "Lead contract exists; lifecycle/storage owner remains fragmented.",
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
        OwnershipAuditStatus.PARTIAL,
        "contracts.product_contract",
        None,
        "Product contract surface exists; entity lifecycle/storage owner is not complete.",
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
        OwnershipAuditStatus.PARTIAL,
        "contracts.product_contract",
        None,
        "Offer is canonically defined in Product Contract, but persistence/storage ownership is not universalized.",
    ),
    _row(
        "Channel",
        OwnershipAuditStatus.PARTIAL,
        "application.business_autonomy.channel_contracts",
        None,
        "Typed channel identity exists; universal business-channel owner is incomplete.",
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
        OwnershipAuditStatus.DUPLICATE,
        None,
        None,
        "Message semantics remain spread across messaging/runtime/marketing surfaces.",
    ),
    _row(
        "Campaign",
        OwnershipAuditStatus.PARTIAL,
        "contracts.campaign",
        None,
        "Campaign contract exists; lifecycle/storage paths remain distributed.",
    ),
    _row(
        "Opportunity",
        OwnershipAuditStatus.PARTIAL,
        "contracts.opportunity",
        None,
        "Opportunity contract exists; multiple detectors/projections remain.",
    ),
    _row("Deal", OwnershipAuditStatus.MISSING, None, None, "No universal Deal owner on main."),
    _row("Order", OwnershipAuditStatus.MISSING, None, None, "No universal Order owner on main."),
    _row(
        "Invoice",
        OwnershipAuditStatus.PARTIAL,
        "billing.commercial_cycle_contract",
        None,
        "Invoice lifecycle exists in billing but is not a universal ontology owner.",
    ),
    _row(
        "Payment",
        OwnershipAuditStatus.DUPLICATE,
        None,
        None,
        "Payment types/contracts exist in several finance/payment surfaces; owner collapse required.",
    ),
    _row(
        "Refund",
        OwnershipAuditStatus.PARTIAL,
        "billing.refund_orchestrator",
        None,
        "Refund flow exists but canonical semantic/storage owner is incomplete.",
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
        OwnershipAuditStatus.DUPLICATE,
        None,
        None,
        "Revenue semantics exist across finance/economics/revenue surfaces.",
    ),
    _row("Asset", OwnershipAuditStatus.MISSING, None, None, "No universal Asset owner on main."),
    _row(
        "Resource",
        OwnershipAuditStatus.MISSING,
        None,
        None,
        "Existing Resource classes are technical/security resources, not universal business resources.",
    ),
    _row(
        "Goal",
        OwnershipAuditStatus.PARTIAL,
        "contracts.business_goal",
        None,
        "Goal contract/planners exist but first-class hierarchy/lifecycle is incomplete.",
    ),
    _row(
        "Constraint",
        OwnershipAuditStatus.PARTIAL,
        "contracts.business_constraints",
        None,
        "BusinessConstraints exists but canonical constraint entity/engine is incomplete.",
    ),
    _row(
        "Risk",
        OwnershipAuditStatus.DUPLICATE,
        None,
        None,
        "Risk representations exist across safety/economics/governance without one universal owner.",
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
        None,
        "ActionIntent is canonical AI-to-execution interface and runtime executor is the side-effect gateway, but neither is itself a canonical storage owner.",
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
        OwnershipAuditStatus.DUPLICATE,
        None,
        None,
        "Strong capability machinery exists but several registries/surfaces require canonical hardening.",
    ),
    _row(
        "Provider",
        OwnershipAuditStatus.PARTIAL,
        "application.business_autonomy.provider_catalog",
        None,
        "Provider catalog is canonical for business autonomy integrations; universal provider ontology remains incomplete.",
    ),
    _row(
        "Policy",
        OwnershipAuditStatus.PARTIAL,
        "contracts.policy_decision",
        None,
        "PolicyDecision is canonical verdict; Policy entity/version ownership remains distributed.",
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
