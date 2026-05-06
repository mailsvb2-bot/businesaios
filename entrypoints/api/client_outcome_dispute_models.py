from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_CLIENT_OUTCOME_DISPUTE_API_MODELS = True


class ClientOutcomeBillableRecordInput(BaseModel):
    record_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    lead_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    verified_at: str = Field(min_length=1)
    unit_price: float
    currency: str = Field(min_length=1)
    quantity: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenClientOutcomeDisputeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    lead_id: str = Field(min_length=1)
    opened_by: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    notes: str = ''
    record: ClientOutcomeBillableRecordInput
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReverseClientOutcomeDisputeRequest(BaseModel):
    dispute_id: str = Field(min_length=1)
    record: ClientOutcomeBillableRecordInput
    reversal_amount: float | None = None


class ClientOutcomeDisputeResponse(BaseModel):
    dispute_id: str
    status: str
    reason_code: str
    resolution_code: str
    classification_case_type: str = ''
    classification_severity: str = ''
    evidence_fingerprint: str = ''


class ClientOutcomeReversalResponse(BaseModel):
    dispute_id: str
    status: str
    negative_record_id: str | None = None
    reversal_id: str | None = None
    ledger_posting_id: str | None = None
    amount: float | None = None
    currency: str | None = None
    partial_reversal: bool = False
    refund_preview: dict[str, Any] | None = None
