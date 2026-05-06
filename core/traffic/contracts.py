from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TrafficObjective:
    """What we maximize."""
    kind: str  # "leads" | "purchases" | "profit"
    target_cac_minor: int = 0
    currency: str = "RUB"


@dataclass(frozen=True)
class TrafficBudget:
    daily_budget_minor: int
    currency: str


@dataclass(frozen=True)
class TrafficCreative:
    headline: str
    primary_text: str
    cta: str = "Learn more"


@dataclass(frozen=True)
class TrafficAudience:
    region: str
    interests: List[str]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class TrafficCampaignSpec:
    name: str
    objective: TrafficObjective
    budget: TrafficBudget
    audience: TrafficAudience
    creative: TrafficCreative
    destination: Dict[str, Any]  # e.g. tg bot deep link / landing url


@dataclass(frozen=True)
class TrafficPlan:
    """Platform-agnostic plan.

    The executor translates this into AdsService spec (commands) for a given platform.
    """
    platform: str
    account_id: str
    campaign: TrafficCampaignSpec
    notes: str = ""
    metadata: Optional[Dict[str, Any]] = None
