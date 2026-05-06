from __future__ import annotations

from pydantic import BaseModel, Field


class CEORequest(BaseModel):
    enabled: bool = False
    objective: str | None = None
    horizon: str = Field(default="30d", min_length=1)
    risk_level: str = Field(default="conservative", min_length=1)


class ExecuteGoalRequest(BaseModel):
    goal: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    tenant_id: str = Field(default="default", min_length=1)
    user_id: str | None = None
    region: str = Field(default="global", min_length=1)
    max_steps: int = Field(default=1, ge=1, le=20)
    profile: dict = Field(default_factory=dict)
    signals: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    economy: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)
    ceo: CEORequest = Field(default_factory=CEORequest)


class ExecuteGoalStepResponse(BaseModel):
    step_index: int
    decision_id: str
    action_id: str
    action: str
    status: str
    ok: bool
    correlation_id: str | None = None
    reason: str | None = None
    payload: dict = Field(default_factory=dict)
    feedback: dict = Field(default_factory=dict)
    capability_view: dict = Field(default_factory=dict)


class ExecuteGoalResponse(BaseModel):
    goal: str
    business_id: str
    tenant_id: str
    completed: bool
    stop_reason: str
    steps: list[ExecuteGoalStepResponse] = Field(default_factory=list)
    final_feedback: dict = Field(default_factory=dict)
    capability_view: dict = Field(default_factory=dict)
