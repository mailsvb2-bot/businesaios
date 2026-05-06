from __future__ import annotations

from pydantic import BaseModel, Field


class DriftAuditRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    candidate_run_id: str = Field(min_length=1)


class DriftAuditResponse(BaseModel):
    severity: str
    goal_score_delta: float
    report_text: str


class RollbackBaselineRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    fallback_run_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RollbackBaselineResponse(BaseModel):
    baseline_name: str
    source_run_id: str
    rollback_reason: str
