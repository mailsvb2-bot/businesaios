from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.economics.objective import DEFAULT_OBJECTIVE, normalize_objective

Json = Dict[str, Any]

EXPECTED_AUTOPILOT_RUNTIME_ACTION = "ads_autopilot_tick@v1"
EXPECTED_DECISION_ISSUER = "businesaios-core"


@dataclass(frozen=True)
class AdsAutopilotConstraints:
    max_daily_budget_minor: int = 0
    currency: str = "RUB"

    max_spend_minor: int = 0
    max_cpa_minor: int = 0
    min_roas_x1000: int = 0

    allowed_platforms: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if int(self.max_daily_budget_minor) < 0:
            raise ValueError("constraints.max_daily_budget_minor must be >= 0")
        if int(self.max_spend_minor) < 0:
            raise ValueError("constraints.max_spend_minor must be >= 0")
        if int(self.max_cpa_minor) < 0:
            raise ValueError("constraints.max_cpa_minor must be >= 0")
        if int(self.min_roas_x1000) < 0:
            raise ValueError("constraints.min_roas_x1000 must be >= 0")
        if not str(self.currency or "").strip():
            raise ValueError("constraints.currency is required")


@dataclass(frozen=True)
class AdsAutopilotRequest:
    tenant_id: str
    objective: str = DEFAULT_OBJECTIVE

    offer: Json = field(default_factory=dict)
    audience: Json = field(default_factory=dict)
    channels: List[str] = field(default_factory=list)

    constraints: AdsAutopilotConstraints = field(default_factory=AdsAutopilotConstraints)

    dry_run: bool = True
    plan_only: bool = True
    apply_enabled: bool = False

    correlation_id: str = ""
    decision_id: str = ""

    # Canonical routing metadata: proves request came from DecisionCore-issued envelope.
    issuer_id: str = ""
    issued_action: str = ""
    route: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", normalize_objective(self.objective))

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.objective or "").strip():
            raise ValueError("objective is required")
        self.constraints.validate()

    def validate_executor_route(self) -> None:
        if not str(self.decision_id or "").strip():
            raise ValueError("decision_id is required for ads autopilot runtime execution")
        if not str(self.correlation_id or "").strip():
            raise ValueError("correlation_id is required for ads autopilot runtime execution")
        if not str(self.issuer_id or "").strip():
            raise ValueError("issuer_id is required for ads autopilot runtime execution")
        if str(self.issuer_id) != EXPECTED_DECISION_ISSUER:
            raise ValueError(f"issuer_id must be {EXPECTED_DECISION_ISSUER!r}")
        if str(self.issued_action or "").strip() != EXPECTED_AUTOPILOT_RUNTIME_ACTION:
            raise ValueError(
                f"issued_action must be {EXPECTED_AUTOPILOT_RUNTIME_ACTION!r}"
            )
        if not str(self.route or "").strip():
            raise ValueError("route metadata is required for ads autopilot runtime execution")

    def allow_apply(self) -> bool:
        return bool(self.apply_enabled) and not bool(self.dry_run) and not bool(self.plan_only)


@dataclass(frozen=True)
class AdsAutopilotResponse:
    status: str
    stop_loss: Json
    plan: Json
    applied: Json
    notes: str = ""