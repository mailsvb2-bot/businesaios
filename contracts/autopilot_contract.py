from __future__ import annotations

"""Business Autopilot Contract (canonical).

This contract is *above* Product Contract.

Product Contract answers: "what is the product?" (domain, offers, pricing pointer).
Autopilot Contract answers: "what is the business objective and what may be changed safely?"

Design rules:
- Declarative, deterministic, validated.
- No implicit behavior. Runtime + DecisionCore consume it.
- No side effects here.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AutopilotConstraints:
    """Hard constraints (budget/limits/pace).

    Values are per-tenant defaults; runtime may further tighten per-user.
    """

    # Pace
    max_price_changes_per_day: int = 1
    cooldown_hours: int = 24

    # Budget guardrails (for future ads connectors)
    daily_budget_minor: int = 0
    currency: str = "RUB"

    def validate(self) -> None:
        if int(self.max_price_changes_per_day) <= 0:
            raise ValueError("constraints.max_price_changes_per_day must be > 0")
        if int(self.cooldown_hours) < 0:
            raise ValueError("constraints.cooldown_hours must be >= 0")
        if int(self.daily_budget_minor) < 0:
            raise ValueError("constraints.daily_budget_minor must be >= 0")
        if not str(self.currency or "").strip():
            raise ValueError("constraints.currency is required")


@dataclass(frozen=True)
class DataRequirements:
    """Minimum telemetry required for safe optimization."""

    required_event_types: tuple[str, ...] = (
        # Funnel primitives (internal)
        "lead_created@v1",
        "purchase_completed@v1",
    )
    optional_event_types: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.required_event_types:
            raise ValueError("data_requirements.required_event_types must be non-empty")


@dataclass(frozen=True)
class AutopilotCapabilities:
    """Backward-compatible name for the canonical control surface.

    Historically this surface was exposed as capabilities. The canonical
    semantics did not change, only the name became more precise. Keeping a
    dedicated dataclass preserves older imports without introducing a second
    decision model.
    """

    can_change_offer: bool = True
    can_change_price: bool = True
    can_change_copy: bool = True
    can_change_frequency: bool = True


@dataclass(frozen=True)
class ControlSurface(AutopilotCapabilities):
    """What the Autopilot may change."""

    can_change_offer: bool = True
    can_change_price: bool = True
    can_change_copy: bool = True
    can_change_frequency: bool = True


@dataclass(frozen=True)
class SafetyPolicy:
    """Safety rails.

    stop_loss_* are evaluated on read-model metrics; when triggered,
    DecisionCore must back off to audit mode (no changes) and request human action.
    """

    stop_loss_max_cac_minor: int = 0  # 0 means "unknown" / disabled
    stop_loss_min_profit_minor: int = 0  # if < 0 for N days -> stop
    # Rolling window length for stop-loss evaluation (in days).
    stop_loss_cac_days: int = 1
    stop_loss_profit_days: int = 1

    # Ads-style stop-loss (optional). When set (>0), if spend_minor_window
    # exceeds this and conversions_window==0, autopilot must back off.
    stop_loss_max_spend_minor_no_conv: int = 0
    stop_loss_no_conv_days: int = 1
    allow_channels: tuple[str, ...] = ("internal",)

    def validate(self) -> None:
        if int(self.stop_loss_max_cac_minor) < 0:
            raise ValueError("safety.stop_loss_max_cac_minor must be >= 0")
        if not self.allow_channels:
            raise ValueError("safety.allow_channels must be non-empty")


@dataclass(frozen=True)
class AutopilotContract:
    """Canonical Autopilot contract.

    north_star_metric: what we maximize.
    """

    contract_id: str
    tenant_id: str
    # What we maximize. Keep vocabulary small but extensible.
    # Canonical set is validated below.
    north_star_metric: str = "profit"  # profit | revenue | retention | ltv | cac | activation_rate

    constraints: AutopilotConstraints = AutopilotConstraints()
    data_requirements: DataRequirements = DataRequirements()
    control_surface: ControlSurface = ControlSurface()
    safety_policy: SafetyPolicy = SafetyPolicy()

    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.contract_id or "").strip():
            raise ValueError("contract_id is required")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        allowed = {"profit", "revenue", "retention", "ltv", "cac", "activation_rate"}
        if str(self.north_star_metric or "").strip() not in allowed:
            raise ValueError(
                "north_star_metric must be one of: profit, revenue, retention, ltv, cac, activation_rate"
            )
        self.constraints.validate()
        self.data_requirements.validate()
        self.safety_policy.validate()

__all__ = [
    "AutopilotCapabilities",
    "AutopilotConstraints",
    "AutopilotContract",
    "ControlSurface",
    "DataRequirements",
    "SafetyPolicy",
]
