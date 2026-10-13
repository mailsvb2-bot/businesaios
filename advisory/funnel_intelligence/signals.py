from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _probability(value: object) -> float:
    return max(0.0, min(float(value), 1.0))


@dataclass(frozen=True, slots=True)
class ConversationSignals:
    """Derived evidence only; never a replacement for Customer/World Model state."""

    intent: str = "other"
    need_summary: str = ""
    need_specificity: float = 0.0
    buying_readiness: float = 0.0
    purchase_intent: float = 0.0
    trust: float = 0.5
    engagement: float = 0.0
    urgency: float = 0.0
    price_sensitivity: float = 0.0
    negative_sentiment: float = 0.0
    confusion: float = 0.0
    uncertainty: float = 0.0
    friction: float = 0.0
    confidence: float = 0.0
    sales_pressure_tolerance: float = 0.5
    preferred_channel: str | None = None
    preferred_response_length: str | None = None
    preferred_tone: str | None = None

    def __post_init__(self) -> None:
        numeric = (
            "need_specificity",
            "buying_readiness",
            "purchase_intent",
            "trust",
            "engagement",
            "urgency",
            "price_sensitivity",
            "negative_sentiment",
            "confusion",
            "uncertainty",
            "friction",
            "confidence",
            "sales_pressure_tolerance",
        )
        for name in numeric:
            object.__setattr__(self, name, _probability(getattr(self, name)))

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "ConversationSignals":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in values.items() if key in allowed})


@dataclass(frozen=True, slots=True)
class FatigueInputs:
    same_argument_count: int = 0
    same_cta_count: int = 0
    messages_24h: int = 0
    messages_7d: int = 0
    unanswered_outbound: int = 0


def fatigue_score(inputs: FatigueInputs) -> float:
    raw = (
        0.10 * max(inputs.same_argument_count - 1, 0)
        + 0.12 * max(inputs.same_cta_count - 1, 0)
        + 0.08 * max(inputs.messages_24h - 1, 0)
        + 0.02 * max(inputs.messages_7d - 3, 0)
        + 0.18 * max(inputs.unanswered_outbound, 0)
    )
    return max(0.0, min(raw, 1.0))


@dataclass(frozen=True, slots=True)
class PressureInputs:
    purchase_intent: float = 0.0
    positive_outcome: float = 0.0
    pricing_interest: float = 0.0
    checkout_activity: float = 0.0
    negative_sentiment: float = 0.0
    unanswered_outbound: float = 0.0
    unresolved_objection: float = 0.0
    recent_followup: float = 0.0
    complaint: float = 0.0
    hesitation: float = 0.0


def pressure_budget(inputs: PressureInputs) -> float:
    positive = (
        0.24 * inputs.purchase_intent
        + 0.20 * inputs.positive_outcome
        + 0.15 * inputs.pricing_interest
        + 0.20 * inputs.checkout_activity
    )
    negative = (
        0.22 * inputs.negative_sentiment
        + 0.15 * inputs.unanswered_outbound
        + 0.22 * inputs.unresolved_objection
        + 0.10 * inputs.recent_followup
        + 0.25 * inputs.complaint
        + 0.12 * inputs.hesitation
    )
    return max(0.0, min(1.0, 0.35 + positive - negative))
