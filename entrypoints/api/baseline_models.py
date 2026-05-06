from __future__ import annotations

from pydantic import BaseModel, Field


class PromoteBaselineRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    label: str = Field(default="api", min_length=1)


class PromoteBaselineResponse(BaseModel):
    baseline_name: str
    source_run_id: str
    goal: str
    business_id: str
    tenant_id: str
    promoted_at_label: str
    metadata: dict = Field(default_factory=dict)


class SelectBaselineRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1)


class SelectBaselineResponse(BaseModel):
    selected_run_id: str | None = None
    completed: bool | None = None
    stop_reason: str | None = None
    goal_score: float | None = None
