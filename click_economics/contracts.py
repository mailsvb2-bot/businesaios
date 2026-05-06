from __future__ import annotations

from dataclasses import dataclass


CANON_CLICK_ECONOMICS_CONTRACT = True


@dataclass(frozen=True, slots=True)
class ClickCommercialFact:
    tenant_id: str
    business_id: str
    entity_id: str
    source_channel: str
    click_id: str = ''
    session_id: str = ''
    tracking_token: str = ''
    status: str = 'unknown'
    paid_channel: bool = False
    billable_candidate: bool = False
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False



@dataclass(frozen=True, slots=True)
class ClickBillableFact:
    tenant_id: str
    business_id: str
    entity_id: str
    amount_minor: int
    currency: str
    source_channel: str
    click_id: str = ''
    session_id: str = ''
    tracking_token: str = ''
    reason_code: str = 'qualified_click'
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_billing: bool = False
    ready_for_export: bool = False



@dataclass(frozen=True, slots=True)
class ClickBillingHandoffRecord:
    tenant_id: str
    business_id: str
    entity_id: str
    status: str = 'pending'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    handoff_contract: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClickBillingInvoicePreview:
    tenant_id: str
    business_id: str
    entity_id: str
    invoice_id: str
    currency: str
    total_minor: int
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    invoice_preview: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClickBillingCollectionPreview:
    tenant_id: str
    business_id: str
    entity_id: str
    invoice_id: str
    provider_name: str = ''
    currency: str = 'USD'
    total_minor: int = 0
    collectible_amount_minor: int = 0
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    collection_preview: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClickBillingExecutionRecord:
    tenant_id: str
    business_id: str
    entity_id: str
    invoice_id: str
    provider_name: str = ''
    currency: str = 'USD'
    total_minor: int = 0
    collected_amount_minor: int = 0
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    execution_result: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClickBillingSettlementRecord:
    tenant_id: str
    business_id: str
    entity_id: str
    invoice_id: str
    provider_name: str = ''
    currency: str = 'USD'
    collected_amount_minor: int = 0
    settled_amount_minor: int = 0
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    settlement_result: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClickBillingProviderDispatchRecord:
    tenant_id: str
    business_id: str
    entity_id: str
    invoice_id: str
    provider_name: str = ''
    currency: str = 'USD'
    settled_amount_minor: int = 0
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    provider_dispatch: dict[str, object] | None = None
