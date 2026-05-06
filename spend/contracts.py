from __future__ import annotations

from dataclasses import dataclass


CANON_SPEND_CONTRACT = True


@dataclass(frozen=True, slots=True)
class SpendFact:
    tenant_id: str
    business_id: str
    entity_id: str
    amount_minor: int
    unit_cost_minor: int | None
    source_channel: str = ''
    status: str = 'missing'
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False



@dataclass(frozen=True, slots=True)
class SpendSourceFact:
    tenant_id: str
    business_id: str
    entity_id: str
    source_channel: str = ''
    source_kind: str = 'unknown'
    tracking_token: str = ''
    click_id: str = ''
    session_id: str = ''
    status: str = 'missing'
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False


@dataclass(frozen=True, slots=True)
class SpendSourceIngressRecord:
    tenant_id: str
    business_id: str
    entity_id: str
    source_channel: str = ''
    source_kind: str = 'unknown'
    tracking_token: str = ''
    click_id: str = ''
    session_id: str = ''
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False


@dataclass(frozen=True, slots=True)
class SpendIngressEnvelope:
    tenant_id: str
    business_id: str
    entity_id: str
    amount_minor: int = 0
    currency: str = 'USD'
    source_channel: str = ''
    source_kind: str = 'unknown'
    tracking_token: str = ''
    click_id: str = ''
    session_id: str = ''
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False


@dataclass(frozen=True, slots=True)
class SpendExternalIngressBatch:
    tenant_id: str
    business_id: str
    entity_id: str
    batch_id: str
    amount_minor: int = 0
    currency: str = 'USD'
    source_channel: str = ''
    source_kind: str = 'unknown'
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    batch_payload: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class SpendExternalIngressRuntimeRequest:
    tenant_id: str
    business_id: str
    entity_id: str
    batch_id: str
    amount_minor: int = 0
    currency: str = 'USD'
    status: str = 'blocked'
    blockers: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
    runtime_request: dict[str, object] | None = None
