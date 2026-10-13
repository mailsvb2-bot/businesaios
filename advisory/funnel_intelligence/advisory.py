from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .contracts import (
    CommercialEvidence,
    DerivedConversationStage,
    FollowupConstraintAssessment,
    FollowupConstraintContext,
    IngressAssessment,
    IngressClassification,
    OfferEvidenceAssessment,
    ScopedInboundEvidence,
    VerifiedOfferEvidence,
)
from .source_order import source_order_is_newer


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
