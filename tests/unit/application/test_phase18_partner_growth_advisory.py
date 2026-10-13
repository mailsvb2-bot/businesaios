from dataclasses import replace

import pytest

from application.partner.growth_advisory import (
    ContactBasis,
    PartnerOpportunity,
    prepare_partner_proposal,
    score_partner_opportunity,
)
from contracts.partner import Partner, PartnerPartyKind, PartnerStatus


def partner(**kwargs):
    return Partner(
        partner_id="partner-a", tenant_id="tenant-a", business_id="business-a",
        party_kind=PartnerPartyKind.ORGANIZATION, party_id="org-a", **kwargs,
    )


def opportunity(**kwargs):
    values = dict(
        partner_id="partner-a", business_id="business-a", name="Health media",
        topics=("psychology", "wellness"), audience_summary="Psychology audience",
        recent_topic="Burnout awareness", followers=8000,
        contact_basis=ContactBasis.OPTED_IN, contact_value="owner@example.org",
        source_url="https://example.org/partners",
    )
    values.update(kwargs)
    return PartnerOpportunity(**values)


def test_partner_donor_scoring_favors_topic_fit_and_proves_contact_basis():
    result = score_partner_opportunity(
        partner=partner(), candidate=opportunity(), audience_terms=("psychology",),
    )
    assert result.fit > 80
    assert result.eligible_for_manual_review
    assert result.eligible_for_automatic_contact
    assert "strong_audience_overlap" in result.reasons


@pytest.mark.parametrize("basis", [
    ContactBasis.PUBLIC_BUSINESS_CONTACT, ContactBasis.UNKNOWN, ContactBasis.NONE,
])
def test_public_contacts_are_never_automatic_send_authority(basis):
    candidate = opportunity(contact_basis=basis)
    result = score_partner_opportunity(
        partner=partner(), candidate=candidate, audience_terms=("psychology",),
    )
    assert not result.eligible_for_automatic_contact
    assert "first_contact_not_authorized" in result.reasons


def test_donor_scoring_penalizes_direct_competitors_and_very_large_audiences():
    matched = score_partner_opportunity(
        partner=partner(), candidate=opportunity(), audience_terms=("psychology",),
    )
    competitor = score_partner_opportunity(
        partner=partner(), candidate=opportunity(competitor=True, followers=2_000_000),
        audience_terms=("psychology",),
    )
    assert competitor.fit < matched.fit
    assert competitor.risk >= 73
    assert not competitor.eligible_for_manual_review


def test_existing_canonical_partner_scope_and_archive_are_enforced():
    with pytest.raises(PermissionError):
        score_partner_opportunity(
            partner=partner(), candidate=opportunity(business_id="another-business"),
            audience_terms=("psychology",),
        )
    archived = replace(
        partner(), status=PartnerStatus.ARCHIVED, archived_at_ms=5,
    )
    with pytest.raises(PermissionError):
        prepare_partner_proposal(
            partner=archived, candidate=opportunity(),
            business_name="Studio", offering="Course",
            campaign_topic="Burnout", target_url="https://example.org",
        )


def test_truthful_copy_never_claims_consent_or_invents_provider_success():
    draft = prepare_partner_proposal(
        partner=partner(), candidate=opportunity(contact_basis=ContactBasis.UNKNOWN),
        business_name="Studio", offering="Training",
        campaign_topic="Burnout", target_url="https://example.org/course",
    )
    assert draft.requires_human_approval
    assert "Burnout" in draft.outreach_draft
    assert "https://example.org/course" in draft.joint_content_draft
    assert "согласованию" in draft.outreach_draft


@pytest.mark.parametrize("bad", [
    {"followers": float("nan")},
    {"followers": True},
    {"source_url": "http://example.org/partner"},
    {"source_url": "https://u:p@example.org/partner"},
    {"contact_value": "x\nBcc: other@example.org"},
    {"business_id": ""},
    {"topics": tuple("topic" for _ in range(60))},
])
def test_untrusted_partner_discovery_payload_is_rejected(bad):
    with pytest.raises(ValueError):
        opportunity(**bad)


def test_outreach_link_must_be_secure():
    with pytest.raises(ValueError):
        prepare_partner_proposal(
            partner=partner(), candidate=opportunity(),
            business_name="Studio", offering="Training",
            campaign_topic="Burnout", target_url="http://example.org",
        )
