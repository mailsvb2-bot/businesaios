from __future__ import annotations

"""Canonical advisory owner surface for acquisition, revenue and funnel evidence."""

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from advisory.acquisition_recommendation_builder import (
    AcquisitionRecommendation,
    AcquisitionRecommendations,
    CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER,
    build_acquisition_recommendations,
)
from advisory.acquisition_result_copy_renderer import (
    CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER,
    RenderedAcquisitionExplanation,
    render_acquisition_explanation,
)
from advisory.acquisition_result_projection import (
    AcquisitionExplanation,
    CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION,
    explain_acquisition_result,
)
from advisory.revenue_os import (
    CANON_ADVISORY_REVENUE_OS_OWNER_SURFACE,
    RevenueOSFacade,
    RevenueOSReport,
)

CANON_ADVISORY_OWNER_SURFACE = True

def _required(value: object, field: str, maximum: int = 240) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{field} must be 1..{maximum} characters")
    return text


class IngressClassification(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ScopedInboundEvidence:
    tenant_id: str
    subject_id: str
    channel: str
    provider_event_id: str
    source_order_key: str
    text: str
    purpose: str = "sales"

    def __post_init__(self) -> None:
        for name in ("tenant_id", "subject_id", "channel", "provider_event_id", "source_order_key"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        normalized = " ".join(str(self.text or "").replace("\x00", " ").split())
        if not normalized:
            raise ValueError("text must not be empty")
        object.__setattr__(self, "text", normalized[:12000])
        object.__setattr__(self, "purpose", _required(self.purpose, "purpose", 80))

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        return (self.tenant_id, self.channel, self.subject_id, self.provider_event_id)


@dataclass(frozen=True, slots=True)
class IngressAssessment:
    classification: IngressClassification
    reason: str

    @property
    def usable_as_new_evidence(self) -> bool:
        return self.classification is IngressClassification.NEW


class DerivedConversationStage(StrEnum):
    DISCOVERED = "discovered"
    ENGAGED = "engaged"
    NEED_KNOWN = "need_known"
    QUALIFIED = "qualified"
    OFFER_PRESENTED = "offer_presented"
    CHECKOUT = "checkout"
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class CommercialEvidence:
    inbound_seen: bool = False
    contact_seen: bool = False
    need_captured: bool = False
    qualified: bool = False
    offer_presented: bool = False
    checkout_requested: bool = False
    checkout_created: bool = False
    payment_confirmed: bool = False
    declined: bool = False


@dataclass(frozen=True, slots=True)
class VerifiedOfferEvidence:
    offer_id: str
    title: str
    active: bool
    amount_minor: int | None = None
    currency: str | None = None
    availability: str = "available"
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "offer_id", _required(self.offer_id, "offer_id"))
        object.__setattr__(self, "title", _required(self.title, "title", 500))
        if self.revision < 1:
            raise ValueError("offer revision must be >=1")
        if self.amount_minor is not None:
            if isinstance(self.amount_minor, bool) or int(self.amount_minor) < 0:
                raise ValueError("amount_minor must be non-negative")
            object.__setattr__(self, "amount_minor", int(self.amount_minor))
        if (self.amount_minor is None) != (self.currency is None):
            raise ValueError("price requires amount and currency together")
        if self.currency is not None:
            cur = str(self.currency).upper().strip()
            if not re.fullmatch(r"[A-Z]{3}", cur):
                raise ValueError("currency must be ISO-4217 alpha-3")
            object.__setattr__(self, "currency", cur)

    @property
    def sellable(self) -> bool:
        return self.active and self.availability == "available"

    @property
    def has_verified_price(self) -> bool:
        return self.amount_minor is not None and self.currency is not None


@dataclass(frozen=True, slots=True)
class OfferEvidenceAssessment:
    usable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FollowupConstraintContext:
    replied: bool = False
    booked: bool = False
    paid: bool = False
    opted_out: bool = False
    lead_closed: bool = False
    contact_allowed: bool = True
    channel_available: bool = True
    sent_in_sequence: int = 0
    max_sequence: int = 3
    fatigue: float = 0.0
    sent_24h: int = 0
    max_24h: int = 3
    sent_7d: int = 0
    max_7d: int = 8
    last_sent_at: datetime | None = None
    minimum_gap: timedelta = timedelta(0)
    channel_last_sent_at: datetime | None = None
    channel_minimum_gap: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if min(self.sent_in_sequence, self.max_sequence, self.sent_24h, self.max_24h, self.sent_7d, self.max_7d) < 0:
            raise ValueError("contact counters and caps must be non-negative")
        object.__setattr__(self, "fatigue", max(0.0, min(float(self.fatigue), 1.0)))
        if self.minimum_gap < timedelta(0) or self.channel_minimum_gap < timedelta(0):
            raise ValueError("minimum gaps must be non-negative")


@dataclass(frozen=True, slots=True)
class FollowupConstraintAssessment:
    blocked: bool
    reasons: tuple[str, ...]
    defer_until: datetime | None = None


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


class SalesAIIntent(StrEnum):
    SERVICE_INTEREST = "service_interest"
    PRICING = "pricing"
    BOOKING = "booking"
    SUPPORT = "support"
    COMPLAINT = "complaint"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class SalesAIReplyGoal(StrEnum):
    ASK_QUALIFICATION = "ask_qualification"
    ANSWER_QUESTION = "answer_question"
    RESOLVE_ISSUE = "resolve_issue"
    PRESENT_OPTION = "present_option"
    HELP_CHECKOUT = "help_checkout"
    HANDOFF = "handoff"
    NOOP = "noop"


_SALES_AI_OBSERVATION_KEYS = frozenset(
    {
        "intent",
        "need_summary",
        "purchase_readiness",
        "confidence",
        "pricing_question",
        "pricing_exception",
        "need_is_specific",
        "purchase_intent_explicit",
        "explicit_human_request",
        "sensitive_context",
        "negative_sentiment",
        "reply_goal",
        "reason",
    }
)


def _strict_probability(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number between 0 and 1")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number between 0 and 1") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be a finite number between 0 and 1")
    return number


def _strict_bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


@dataclass(frozen=True, slots=True)
class SalesAIObservation:
    """Strict provider-derived evidence; DecisionCore still owns every action."""

    intent: SalesAIIntent = SalesAIIntent.OTHER
    need_summary: str = ""
    purchase_readiness: float = 0.0
    confidence: float = 0.0
    pricing_question: bool = False
    pricing_exception: bool = False
    need_is_specific: bool = False
    purchase_intent_explicit: bool = False
    explicit_human_request: bool = False
    sensitive_context: bool = False
    negative_sentiment: bool = False
    reply_goal: SalesAIReplyGoal = SalesAIReplyGoal.ASK_QUALIFICATION
    reason: str = ""

    def __post_init__(self) -> None:
        intent = self.intent if isinstance(self.intent, SalesAIIntent) else SalesAIIntent(str(self.intent))
        reply_goal = (
            self.reply_goal
            if isinstance(self.reply_goal, SalesAIReplyGoal)
            else SalesAIReplyGoal(str(self.reply_goal))
        )
        summary = " ".join(str(self.need_summary or "").replace("\x00", " ").split())
        reason = " ".join(str(self.reason or "").replace("\x00", " ").split())
        if len(summary) > 600:
            raise ValueError("need_summary must be at most 600 characters")
        if len(reason) > 600:
            raise ValueError("reason must be at most 600 characters")
        object.__setattr__(self, "intent", intent)
        object.__setattr__(self, "reply_goal", reply_goal)
        object.__setattr__(self, "need_summary", summary)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "purchase_readiness",
            _strict_probability(self.purchase_readiness, field="purchase_readiness"),
        )
        object.__setattr__(
            self,
            "confidence",
            _strict_probability(self.confidence, field="confidence"),
        )
        for field_name in (
            "pricing_question",
            "pricing_exception",
            "need_is_specific",
            "purchase_intent_explicit",
            "explicit_human_request",
            "sensitive_context",
            "negative_sentiment",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_bool(getattr(self, field_name), field=field_name),
            )
        if (
            reply_goal is SalesAIReplyGoal.HANDOFF
            and self.confidence >= 0.72
            and not (
                self.explicit_human_request
                or self.sensitive_context
                or self.pricing_exception
                or self.negative_sentiment
            )
        ):
            raise ValueError("high-confidence handoff requires a concrete handoff signal")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "SalesAIObservation":
        actual = set(payload)
        if actual != _SALES_AI_OBSERVATION_KEYS:
            missing = sorted(_SALES_AI_OBSERVATION_KEYS - actual)
            extra = sorted(actual - _SALES_AI_OBSERVATION_KEYS)
            raise ValueError(
                f"sales AI observation keys mismatch: missing={missing}; extra={extra}"
            )
        return cls(**{key: payload[key] for key in _SALES_AI_OBSERVATION_KEYS})

    def to_mapping(self) -> dict[str, object]:
        return {
            "intent": self.intent.value,
            "need_summary": self.need_summary,
            "purchase_readiness": self.purchase_readiness,
            "confidence": self.confidence,
            "pricing_question": self.pricing_question,
            "pricing_exception": self.pricing_exception,
            "need_is_specific": self.need_is_specific,
            "purchase_intent_explicit": self.purchase_intent_explicit,
            "explicit_human_request": self.explicit_human_request,
            "sensitive_context": self.sensitive_context,
            "negative_sentiment": self.negative_sentiment,
            "reply_goal": self.reply_goal.value,
            "reason": self.reason,
        }


def parse_sales_ai_observation(raw: object) -> SalesAIObservation:
    try:
        payload = json.loads(str(raw or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("sales AI structured output must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("sales AI structured output must be an object")
    return SalesAIObservation.from_mapping(payload)


def canonical_sales_ai_parameters(observation: SalesAIObservation) -> dict[str, object]:
    """Map model observations to canonical decision inputs, never to actions."""

    return {
        "model_confidence": observation.confidence,
        "unanswered_inbound": observation.reply_goal
        in {
            SalesAIReplyGoal.ANSWER_QUESTION,
            SalesAIReplyGoal.RESOLVE_ISSUE,
            SalesAIReplyGoal.PRESENT_OPTION,
            SalesAIReplyGoal.HELP_CHECKOUT,
        },
        "explicit_human_request": observation.explicit_human_request,
        "sensitive_context": observation.sensitive_context,
        "pricing_exception": observation.pricing_exception,
        "negative_sentiment": observation.negative_sentiment,
        "evidence_score": observation.purchase_readiness,
    }


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


_DECIMAL = re.compile(r"^[0-9]+$")


def compare_source_order(left: object, right: object) -> int:
    """Compare provider-native order keys without lexicographic numeric bugs.

    Decimal provider ids are compared numerically (10 > 9 and 010 == 10).
    Non-decimal keys retain deterministic lexical ordering. Missing keys fail
    closed because freshness cannot be established.
    """

    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        raise ValueError("source order keys must be non-empty")
    if _DECIMAL.fullmatch(a) and _DECIMAL.fullmatch(b):
        ai, bi = int(a), int(b)
        return (ai > bi) - (ai < bi)
    return (a > b) - (a < b)


def source_order_is_newer(incoming: object, current: object) -> bool:
    return compare_source_order(incoming, current) > 0


def assess_inbound_evidence(
    envelope: ScopedInboundEvidence,
    *,
    seen_dedupe_keys=(),
    latest_source_order_key: str | None = None,
) -> IngressAssessment:
    """Classify inbound evidence without ingesting or persisting it."""

    scoped = {tuple(value) for value in seen_dedupe_keys}
    if envelope.dedupe_key in scoped:
        return IngressAssessment(IngressClassification.DUPLICATE, "duplicate_scoped_provider_event")
    if latest_source_order_key is not None and not source_order_is_newer(
        envelope.source_order_key, latest_source_order_key
    ):
        return IngressAssessment(IngressClassification.STALE, "stale_source_order")
    return IngressAssessment(IngressClassification.NEW, "new_evidence")


def derive_conversation_stage(evidence: CommercialEvidence) -> DerivedConversationStage:
    """Derive a projection from canonical evidence; never own conversation state."""

    if evidence.payment_confirmed:
        return DerivedConversationStage.WON
    if evidence.declined:
        return DerivedConversationStage.LOST
    if evidence.checkout_created:
        return DerivedConversationStage.CHECKOUT
    if evidence.offer_presented:
        return DerivedConversationStage.OFFER_PRESENTED
    if evidence.qualified:
        return DerivedConversationStage.QUALIFIED
    if evidence.need_captured:
        return DerivedConversationStage.NEED_KNOWN
    if evidence.inbound_seen or evidence.contact_seen:
        return DerivedConversationStage.ENGAGED
    return DerivedConversationStage.DISCOVERED


def assess_offer_evidence(
    offer: VerifiedOfferEvidence | None,
    *,
    required_revision: int | None = None,
    require_price: bool = False,
) -> OfferEvidenceAssessment:
    reasons: list[str] = []
    if offer is None:
        return OfferEvidenceAssessment(False, ("verified_offer_missing",))
    if not offer.sellable:
        reasons.append("offer_not_sellable")
    if required_revision is not None and offer.revision != int(required_revision):
        reasons.append("offer_revision_stale")
    if require_price and not offer.has_verified_price:
        reasons.append("verified_price_missing")
    return OfferEvidenceAssessment(not reasons, tuple(reasons))


def _quiet_hours_defer_until(
    when: datetime,
    timezone_name: str,
    *,
    start: time,
    end: time,
) -> datetime | None:
    zone = ZoneInfo(timezone_name)
    local = when.astimezone(zone)
    local_time = local.timetz().replace(tzinfo=None)
    if end <= local_time < start:
        return None
    target_date = local.date() + timedelta(days=1 if local_time >= start else 0)
    target = datetime.combine(target_date, end, tzinfo=zone)
    return target.astimezone(when.tzinfo)


def assess_followup_constraints(
    context: FollowupConstraintContext,
    *,
    now: datetime | None = None,
    timezone_name: str | None = None,
    quiet_start: time = time(21),
    quiet_end: time = time(9),
) -> FollowupConstraintAssessment:
    """Return blocking evidence for canonical Policy/ActionIntent owners.

    This function does not authorize dispatch and deliberately has no provider,
    queue, DurableTask or persistence dependency.
    """

    reasons: list[str] = []
    terminal_checks = (
        (context.replied, "reply"),
        (context.booked, "booking"),
        (context.paid, "payment"),
        (context.opted_out, "opt_out"),
        (context.lead_closed, "lead_closed"),
        (not context.contact_allowed, "contact_forbidden"),
        (not context.channel_available, "channel_unavailable"),
        (context.sent_in_sequence >= context.max_sequence, "sequence_frequency_cap"),
        (context.sent_24h >= context.max_24h, "daily_frequency_cap"),
        (context.sent_7d >= context.max_7d, "weekly_frequency_cap"),
        (context.fatigue >= 0.8, "fatigue_cap"),
    )
    reasons.extend(reason for blocked, reason in terminal_checks if blocked)

    defer_until: datetime | None = None
    if now is not None:
        if context.last_sent_at is not None and now - context.last_sent_at < context.minimum_gap:
            reasons.append("minimum_gap")
            defer_until = context.last_sent_at + context.minimum_gap
        if context.channel_last_sent_at is not None and now - context.channel_last_sent_at < context.channel_minimum_gap:
            reasons.append("channel_minimum_gap")
            channel_defer = context.channel_last_sent_at + context.channel_minimum_gap
            if defer_until is None or channel_defer > defer_until:
                defer_until = channel_defer
        if timezone_name:
            quiet_defer = _quiet_hours_defer_until(
                now,
                timezone_name,
                start=quiet_start,
                end=quiet_end,
            )
            if quiet_defer is not None:
                reasons.append("quiet_hours")
                if defer_until is None or quiet_defer > defer_until:
                    defer_until = quiet_defer

    return FollowupConstraintAssessment(bool(reasons), tuple(dict.fromkeys(reasons)), defer_until)




__all__ = [
    "AcquisitionExplanation",
    "AcquisitionRecommendation",
    "AcquisitionRecommendations",
    "CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER",
    "CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER",
    "CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION",
    "CANON_ADVISORY_OWNER_SURFACE",
    "CANON_ADVISORY_REVENUE_OS_OWNER_SURFACE",
    "RevenueOSFacade",
    "RevenueOSReport",
    "RenderedAcquisitionExplanation",
    "build_acquisition_recommendations",
    "explain_acquisition_result",
    "render_acquisition_explanation",
    "CommercialEvidence",
    "ConversationSignals",
    "DerivedConversationStage",
    "FatigueInputs",
    "FollowupConstraintAssessment",
    "FollowupConstraintContext",
    "IngressAssessment",
    "IngressClassification",
    "OfferEvidenceAssessment",
    "PressureInputs",
    "SalesAIIntent",
    "SalesAIObservation",
    "SalesAIReplyGoal",
    "ScopedInboundEvidence",
    "VerifiedOfferEvidence",
    "assess_followup_constraints",
    "assess_inbound_evidence",
    "assess_offer_evidence",
    "canonical_sales_ai_parameters",
    "compare_source_order",
    "derive_conversation_stage",
    "fatigue_score",
    "parse_sales_ai_observation",
    "pressure_budget",
    "source_order_is_newer",
]

