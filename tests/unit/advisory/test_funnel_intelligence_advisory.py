from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from advisory import (
    CommercialEvidence,
    DerivedConversationStage,
    FollowupConstraintContext,
    SalesAIObservation,
    SalesAIReplyGoal,
    ScopedInboundEvidence,
    VerifiedOfferEvidence,
    assess_followup_constraints,
    assess_inbound_evidence,
    assess_offer_evidence,
    canonical_sales_ai_parameters,
    compare_source_order,
    derive_conversation_stage,
)


def _inbound(**changes):
    values = {
        "tenant_id": "tenant-a",
        "subject_id": "person-1",
        "channel": "telegram",
        "provider_event_id": "event-10",
        "source_order_key": "10",
        "text": "Interested in the offer",
    }
    values.update(changes)
    return ScopedInboundEvidence(**values)


def test_numeric_provider_order_is_not_lexicographic() -> None:
    assert compare_source_order("10", "9") > 0
    assert compare_source_order("010", "10") == 0


def test_dedupe_scope_includes_tenant_channel_and_subject() -> None:
    event = _inbound()
    seen = {event.dedupe_key}
    assert not assess_inbound_evidence(event, seen_dedupe_keys=seen).usable_as_new_evidence
    other_tenant = _inbound(tenant_id="tenant-b")
    assert assess_inbound_evidence(other_tenant, seen_dedupe_keys=seen).usable_as_new_evidence


def test_stale_provider_order_is_rejected_as_new_evidence() -> None:
    result = assess_inbound_evidence(_inbound(source_order_key="9"), latest_source_order_key="10")
    assert not result.usable_as_new_evidence
    assert result.reason == "stale_source_order"


def test_checkout_request_does_not_project_checkout() -> None:
    evidence = CommercialEvidence(inbound_seen=True, checkout_requested=True)
    assert derive_conversation_stage(evidence) is DerivedConversationStage.ENGAGED
    assert derive_conversation_stage(CommercialEvidence(checkout_created=True)) is DerivedConversationStage.CHECKOUT


def test_payment_and_decline_are_terminal_projection_evidence() -> None:
    assert derive_conversation_stage(CommercialEvidence(payment_confirmed=True)) is DerivedConversationStage.WON
    assert derive_conversation_stage(CommercialEvidence(declined=True)) is DerivedConversationStage.LOST


def test_offer_price_and_revision_fail_closed() -> None:
    offer = VerifiedOfferEvidence("o-1", "Plan", True, revision=2)
    result = assess_offer_evidence(offer, required_revision=1, require_price=True)
    assert not result.usable
    assert result.reasons == ("offer_revision_stale", "verified_price_missing")


def test_valid_verified_offer_is_advisory_usable() -> None:
    offer = VerifiedOfferEvidence("o-1", "Plan", True, amount_minor=9900, currency="rub", revision=3)
    result = assess_offer_evidence(offer, required_revision=3, require_price=True)
    assert result.usable
    assert result.reasons == ()
    assert offer.currency == "RUB"


def test_followup_constraints_block_terminal_and_frequency_conditions() -> None:
    result = assess_followup_constraints(
        FollowupConstraintContext(paid=True, sent_24h=3, max_24h=3)
    )
    assert result.blocked
    assert "payment" in result.reasons
    assert "daily_frequency_cap" in result.reasons


def test_followup_constraints_compute_latest_defer_and_quiet_hours() -> None:
    now = datetime(2026, 10, 5, 22, 30, tzinfo=timezone.utc)
    result = assess_followup_constraints(
        FollowupConstraintContext(
            last_sent_at=now - timedelta(minutes=10),
            minimum_gap=timedelta(hours=2),
        ),
        now=now,
        timezone_name="UTC",
    )
    assert result.blocked
    assert "minimum_gap" in result.reasons
    assert "quiet_hours" in result.reasons
    assert result.defer_until == datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)


def test_invalid_partial_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="price requires amount and currency together"):
        VerifiedOfferEvidence("o-1", "Plan", True, amount_minor=100)


def test_sales_ai_maps_only_observations_into_decision_inputs() -> None:
    params = canonical_sales_ai_parameters(
        SalesAIObservation(
            intent="service_interest",
            purchase_readiness=0.8,
            confidence=0.95,
            explicit_human_request=True,
            reply_goal=SalesAIReplyGoal.ANSWER_QUESTION,
        )
    )
    assert params["model_confidence"] == 0.95
    assert params["evidence_score"] == 0.8
    assert params["unanswered_inbound"] is True
    assert params["explicit_human_request"] is True
    assert "action_kind" not in params
    assert "event" not in params
    assert "status" not in params


def test_sales_ai_high_confidence_handoff_requires_concrete_signal() -> None:
    with pytest.raises(ValueError, match="concrete handoff signal"):
        SalesAIObservation(
            intent="service_interest",
            confidence=0.95,
            reply_goal=SalesAIReplyGoal.HANDOFF,
        )


def test_sales_ai_response_goals_request_response_without_choosing_action() -> None:
    for goal in (
        SalesAIReplyGoal.ANSWER_QUESTION,
        SalesAIReplyGoal.RESOLVE_ISSUE,
        SalesAIReplyGoal.PRESENT_OPTION,
        SalesAIReplyGoal.HELP_CHECKOUT,
    ):
        params = canonical_sales_ai_parameters(
            SalesAIObservation(intent="other", reply_goal=goal)
        )
        assert params["unanswered_inbound"] is True
        assert set(params) == {
            "model_confidence",
            "unanswered_inbound",
            "explicit_human_request",
            "sensitive_context",
            "pricing_exception",
            "negative_sentiment",
            "evidence_score",
        }
