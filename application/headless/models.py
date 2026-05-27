from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from application.autonomy.autonomy_tiers import ALLOWED_AUTONOMY_TIERS

CANON_HEADLESS_MODELS = True


@dataclass(frozen=True)
class CEOParticipation:
    enabled: bool = False
    objective: str | None = None
    horizon: str = "30d"
    risk_level: str = "conservative"
    mode: str = "advisory"

    def validate(self) -> tuple[bool, tuple[str, ...]]:
        issues: list[str] = []
        if self.enabled and self.mode != "advisory":
            issues.append("invalid:ceo.mode")
        if not str(self.horizon or "").strip():
            issues.append("invalid:ceo.horizon")
        if not str(self.risk_level or "").strip():
            issues.append("invalid:ceo.risk_level")
        return (not issues, tuple(issues))


@dataclass(frozen=True)
class GoalExecutionRequest:
    goal: str
    business_id: str
    tenant_id: str = "default"
    user_id: str | None = None
    product_name: str = "BusinesAIOS"
    region: str = "global"
    channel: str = "headless"
    profile: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    ceo: CEOParticipation = field(default_factory=CEOParticipation)
    max_steps: int = 1
    autonomy_tier: str = 'supervised'
    approval_policy: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[bool, tuple[str, ...]]:
        issues: list[str] = []
        if not str(self.goal or "").strip():
            issues.append("missing:goal")
        if not str(self.business_id or "").strip():
            issues.append("missing:business_id")
        if not str(self.tenant_id or "").strip():
            issues.append("missing:tenant_id")
        if not str(self.channel or "").strip():
            issues.append("missing:channel")
        if int(self.max_steps) < 1:
            issues.append("invalid:max_steps")
        if int(self.max_steps) > 20:
            issues.append("invalid:max_steps_too_large")
        if str(self.autonomy_tier or '').strip() not in ALLOWED_AUTONOMY_TIERS:
            issues.append('invalid:autonomy_tier')
        ceo_ok, ceo_issues = self.ceo.validate()
        if not ceo_ok:
            issues.extend(ceo_issues)
        return (not issues, tuple(issues))


@dataclass(frozen=True)
class GoalExecutionStep:
    step_index: int
    decision_id: str
    action_id: str
    action: str
    status: str
    attempted: bool = False
    executed: bool = False
    verified: bool = False
    operator_required: bool = False
    correlation_id: str | None = None
    reason: str | None = None
    verification_status: str | None = None
    external_ref: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)
    execution_feedback: dict[str, Any] = field(default_factory=dict)
    canonical_step_artifact: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Backward-compatible alias.

        Canonical consumers should inspect attempted/executed/verified directly.
        """
        return bool(self.executed)


@dataclass(frozen=True)
class GoalExecutionReport:
    goal: str
    business_id: str
    tenant_id: str
    completed: bool
    stop_reason: str
    steps: tuple[GoalExecutionStep, ...]
    final_feedback: dict[str, Any] = field(default_factory=dict)
    canonical_run_artifact: dict[str, Any] = field(default_factory=dict)

    @property
    def attempted(self) -> bool:
        return bool(self.final_feedback.get("attempted", self.steps[-1].attempted if self.steps else False))

    @property
    def executed(self) -> bool:
        return bool(self.final_feedback.get("executed", self.steps[-1].executed if self.steps else False))

    @property
    def verified(self) -> bool:
        return bool(self.final_feedback.get("verified", self.steps[-1].verified if self.steps else False))

    @property
    def operator_required(self) -> bool:
        return bool(self.final_feedback.get("operator_required", self.steps[-1].operator_required if self.steps else False))


__all__ = [
    "CANON_HEADLESS_MODELS",
    "CEOParticipation",
    "GoalExecutionReport",
    "GoalExecutionRequest",
    "GoalExecutionStep",
]
