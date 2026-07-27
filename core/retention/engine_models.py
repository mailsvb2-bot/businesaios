from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.pricing_retention_policy import DEFAULT_RETENTION_ENGINE_POLICY


@dataclass(frozen=True)
class RetentionDecision:
    offer_id: str
    variant_key: str
    price_rub: int
    score: float = DEFAULT_RETENTION_ENGINE_POLICY.decision_score_floor


@dataclass(frozen=True)
class RetentionDayDecision:
    tenant_id: str
    day_key: str
    day_index: int
    hazard: float
    readiness: float
    offer_arm: str
    offer_price_rub: int | None
    suppressed: bool
    reason: str
    debug: dict[str, Any]


@dataclass(frozen=True)
class RetentionOfferCandidate:
    candidate_id: str
    offer_arm: str
    offer_price_rub: int
    expected_profit_delta_minor: float
    ope_wis: float
    uplift: float
    risk_penalty: float
    propensity: float | None
    debug: dict[str, Any]


@dataclass(frozen=True)
class RetentionEvaluation:
    tenant_id: str
    day_key: str
    day_index: int
    hazard: float
    readiness: float
    suppressed: bool
    reason: str
    candidates: tuple[RetentionOfferCandidate, ...]
    debug: dict[str, Any]
