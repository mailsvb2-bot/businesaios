from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_CLIENT_OUTCOME_CYCLE_API_MODELS = True


class ClientOutcomeLeadInput(BaseModel):
    lead_id: str = Field(min_length=1)
    captured_at: str = Field(min_length=1)
    tracking_token: str = Field(min_length=1)
    source_channel: str = Field(min_length=1)
    session_id: str = ''
    click_id: str = ''
    phone_hash: str = ''
    email_hash: str = ''
    external_customer_id: str = ''
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClientOutcomeProofInput(BaseModel):
    proof_id: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    proof_type: str = Field(min_length=1)
    status: str = Field(min_length=1)
    source: str = Field(min_length=1)
    external_ref: str = ''
    amount: float = 0.0
    currency: str = 'EUR'
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecuteClientOutcomeCycleRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    package_id: str = ''
    requested_clients: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    lead: ClientOutcomeLeadInput
    proofs: tuple[ClientOutcomeProofInput, ...] = Field(default_factory=tuple)
    acquisition_cost: float = 0.0
    dispute_reason_code: str = ''
    dispute_opened_by: str = ''
    dispute_reversal_amount: float | None = None
    idempotency_key: str = ''


class ClientOutcomeVerificationResponse(BaseModel):
    verified: bool
    billable: bool
    reason_code: str
    confidence: float
    attributed: bool
    fraud_score: float
    eligibility_category: str
    proof_refs: tuple[str, ...] = ()


class ClientOutcomeRevenueResponse(BaseModel):
    appended_record_ids: tuple[str, ...] = ()
    rejected_record_ids: tuple[str, ...] = ()
    invoice_line_ids: tuple[str, ...] = ()
    billable_clients: int
    verified_clients: int
    billed_revenue: float
    acquisition_cost: float
    gross_margin: float
    cac: float
    revenue_per_client: float
    margin_per_client: float
    currency: str


class ExecuteClientOutcomeCycleResponse(BaseModel):
    order: dict[str, Any]
    execution: dict[str, Any]
    verification: ClientOutcomeVerificationResponse
    billable_record: dict[str, Any] | None = None
    revenue_before_reversal: ClientOutcomeRevenueResponse
    dispute: dict[str, Any] | None = None
    reversal: dict[str, Any] | None = None
    revenue_after_reversal: ClientOutcomeRevenueResponse
    admin_summary: dict[str, Any]
