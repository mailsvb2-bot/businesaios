from __future__ import annotations
from pydantic import BaseModel, Field
class RollbackRecommendationRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    candidate_run_id: str = Field(min_length=1)
    fallback_run_ids: list[str] = Field(min_length=1)
class RollbackRecommendationResponse(BaseModel):
    baseline_name: str
    candidate_run_id: str
    should_rollback: bool
    confidence: float
    reason: str
    recommended_run_id: str | None = None
class JoinedHistoryRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    candidate_run_ids: list[str] = Field(min_length=1)
class JoinedHistoryResponse(BaseModel):
    payload: dict = Field(default_factory=dict)
class PromotionEvidenceVerifyRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
class PromotionEvidenceVerifyResponse(BaseModel):
    ok: bool
    expected: dict = Field(default_factory=dict)
    observed: dict = Field(default_factory=dict)
class PromoteScenarioBaselineRequest(BaseModel):
    scenario: str = Field(min_length=1)
    run_ids: list[str] = Field(min_length=1)
    suffix: str = Field(default="golden", min_length=1)
    label: str = Field(default="scenario_auto", min_length=1)
class PromoteScenarioBaselineResponse(BaseModel):
    baseline_name: str | None = None
    source_run_id: str | None = None
    goal: str | None = None
    business_id: str | None = None
    tenant_id: str | None = None
    promoted_at_label: str | None = None
    metadata: dict = Field(default_factory=dict)
class RollbackTimelineRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
class RollbackTimelineResponse(BaseModel):
    baseline_name: str
    timeline_text: str
class DriftTrendRequest(BaseModel):
    baseline_name: str = Field(min_length=1)
    candidate_run_ids: list[str] = Field(min_length=1)
class DriftTrendResponse(BaseModel):
    baseline_name: str
    samples: int
    avg_goal_score_delta: float
    high_count: int
    medium_count: int
    low_count: int
    none_count: int
    summary: str
class BusinessMemoryGovernanceSummaryRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
class BusinessMemoryGovernanceSummaryResponse(BaseModel):
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
