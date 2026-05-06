from __future__ import annotations

"""AI CEO contracts (pure).

AI CEO = executive loop that plans and coordinates profit-driving actions.

Design goals:
- tiny, dumb dataclasses
- stable schemas (versioned)
- no side-effects
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class CEOIntentV1:
    """High-level intent.

    Examples:
      - increase_profit
      - steady_roi
      - reduce_risk
    """

    schema_version: int = 1
    kind: str = "increase_profit"
    horizon_days: int = 14
    risk_level: str = "low"  # low/medium/high
    target_profit_delta_minor: Optional[int] = None
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CEOPlanStepV1:
    """A single planned step.

    action: runtime action name (e.g., execute_plan@v1 step action)
    payload: dict that runtime handler expects (idempotency/correlation keys added by DecisionCore)
    """

    schema_version: int = 1
    title: str = ""
    rationale: str = ""
    action: str = "noop@v1"
    payload: Dict[str, Any] = field(default_factory=dict)
    # Optional safety tags for UI / audit
    tags: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class CEOPlanV1:
    """A plan with ordered steps.

    IMPORTANT:
    - purely descriptive
    - execution is an explicit user-approved step
    """

    schema_version: int = 1
    plan_id: str = ""
    intent: CEOIntentV1 = field(default_factory=CEOIntentV1)
    summary: str = ""
    steps: List[CEOPlanStepV1] = field(default_factory=list)
    kpi_before: Dict[str, Any] = field(default_factory=dict)
    kpi_targets: Dict[str, Any] = field(default_factory=dict)