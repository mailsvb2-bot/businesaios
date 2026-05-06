from __future__ import annotations

from pydantic import BaseModel, Field


class BusinessMemoryGetRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)


class BusinessMemorySummaryRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)


class BusinessMemoryRecentRunsRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class BusinessMemoryResponse(BaseModel):
    payload: dict = Field(default_factory=dict)


class BusinessMemorySummaryResponse(BaseModel):
    tenant_id: str
    business_id: str
    total_runs: int
    completed_runs: int
    failed_runs: int
    average_goal_score: float
    active_goals: list[str] = Field(default_factory=list)
    learned_preferences: dict = Field(default_factory=dict)
    recurring_failures: list[str] = Field(default_factory=list)
    recurring_wins: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    trends: dict = Field(default_factory=dict)


class BusinessMemoryRecentRunsResponse(BaseModel):
    runs: list[dict] = Field(default_factory=list)


class BusinessMemoryPatternsResponse(BaseModel):
    patterns: list[dict] = Field(default_factory=list)
