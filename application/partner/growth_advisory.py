"""Partner discovery assessment and truthful outreach preparation.

ClientPlatform's partner scoring/copy rules adapted to the single BusinessAIOS
PartnerRegistry: no parallel campaign store, contact sender or attribution writer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from contracts.partner import Partner, PartnerStatus

CANON_PHASE18_PARTNER_GROWTH_ADVISORY = True


class ContactBasis(StrEnum):
    OPTED_IN = "opted_in"
    EXISTING_RELATIONSHIP = "existing_relationship"
    PUBLIC_BUSINESS_CONTACT = "public_business_contact"
    UNKNOWN = "unknown"
    NONE = "none"

    @property
    def allows_automatic_first_contact(self) -> bool:
        return self in {ContactBasis.OPTED_IN, ContactBasis.EXISTING_RELATIONSHIP}


@dataclass(frozen=True, slots=True)
class PartnerOpportunity:
    partner_id: str
    business_id: str
    name: str
    topics: tuple[str, ...]
    audience_summary: str = ""
    recent_topic: str = ""
    followers: int | None = None
    contact_basis: ContactBasis = ContactBasis.UNKNOWN
    contact_value: str = ""
    source_url: str = ""
    competitor: bool = False

    def __post_init__(self) -> None:
        for field in ("partner_id", "business_id", "name"):
            value = str(getattr(self, field) or "").strip()
            if not value or len(value) > 240 or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"partner_{field}_invalid")
            object.__setattr__(self, field, value)
        object.__setattr__(self, "contact_basis", ContactBasis(self.contact_basis))
        if self.followers is not None and (type(self.followers) is not int or not 0 <= self.followers <= 1_000_000_000):
            raise ValueError("partner_followers_invalid")
        if len(self.topics) > 48 or any(not isinstance(t, str) or len(t) > 100 for t in self.topics):
            raise ValueError("partner_topics_invalid")
        for field in ("contact_value", "audience_summary", "recent_topic", "source_url"):
            value = str(getattr(self, field) or "").strip()
            if len(value) > 2000 or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"partner_{field}_invalid")
            object.__setattr__(self, field, value)
        if self.source_url:
            url = urlsplit(self.source_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError("partner_public_source_requires_https")


@dataclass(frozen=True, slots=True)
class PartnerFitAssessment:
    partner_id: str
    fit: float
    relevance: float
    audience_quality: float
    contactability: float
    collaboration: float
    risk: float
    reasons: tuple[str, ...]
    eligible_for_manual_review: bool
    eligible_for_automatic_contact: bool


@dataclass(frozen=True, slots=True)
class PartnerPreparedProposal:
    partner_id: str
    business_id: str
    outreach_draft: str
    joint_content_draft: str
    requires_human_approval: bool = True


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def _audience_quality(followers: int | None) -> float:
    if followers is None:
        return 55.0
    if followers == 0:
        return 20.0
    distance = abs(math.log10(max(1, followers)) - math.log10(8000))
    return max(30.0, min(100.0, 100.0 - distance * 28.0))


def score_partner_opportunity(
    *, partner: Partner, candidate: PartnerOpportunity,
    audience_terms: tuple[str, ...],
) -> PartnerFitAssessment:
    """Explainable advisory rank; scores never authorize a message or spend."""
    if (partner.status is not PartnerStatus.ACTIVE
            or partner.partner_id != candidate.partner_id
            or partner.business_id != candidate.business_id):
        raise PermissionError("partner_canonical_binding_invalid")
    if len(audience_terms) > 48:
        raise ValueError("partner_audience_terms_excessive")
    sought = {_norm(t) for t in audience_terms if _norm(t)}
    observed = {_norm(t) for t in (
        *candidate.topics, candidate.name,
        candidate.audience_summary, candidate.recent_topic,
    ) if _norm(t)}
    overlap = 0.0 if not sought else sum(
        any(term in text or text in term for text in observed)
        for term in sought
    ) / len(sought)
    relevance = min(100.0, 28.0 + overlap * 72.0) if sought else 55.0
    audience_quality = _audience_quality(candidate.followers)
    contactability = {
        ContactBasis.OPTED_IN: 100.0,
        ContactBasis.EXISTING_RELATIONSHIP: 95.0,
        ContactBasis.PUBLIC_BUSINESS_CONTACT: 82.0,
        ContactBasis.UNKNOWN: 20.0,
        ContactBasis.NONE: 0.0,
    }[candidate.contact_basis]
    if not candidate.contact_value:
        contactability = min(contactability, 10.0)
    collaboration = min(100.0, 50.0
                        + (18.0 if candidate.recent_topic else 0.0)
                        + (12.0 if candidate.audience_summary else 0.0)
                        + (8.0 if candidate.source_url else 0.0))
    risk = (65.0 if candidate.competitor else 0.0) + (
        20.0 if not candidate.contact_basis.allows_automatic_first_contact else 0.0
    ) + (8.0 if candidate.followers is not None and candidate.followers > 1_000_000 else 0.0)
    fit = max(0.0, min(100.0,
                      relevance * 0.40 + audience_quality * 0.20
                      + contactability * 0.20 + collaboration * 0.20 - risk))
    reasons = tuple(reason for condition, reason in (
        (overlap > 0.35, "strong_audience_overlap"),
        (bool(candidate.recent_topic), "recent_topic_available"),
        (candidate.competitor, "direct_competitor"),
        (not candidate.contact_basis.allows_automatic_first_contact, "first_contact_not_authorized"),
        (bool(candidate.contact_basis.allows_automatic_first_contact), "contact_basis_verified"),
    ) if condition)
    safe = bool(candidate.contact_value) and not candidate.competitor
    return PartnerFitAssessment(
        partner_id=partner.partner_id, fit=round(fit, 2),
        relevance=relevance, audience_quality=audience_quality,
        contactability=contactability, collaboration=collaboration,
        risk=min(100.0, risk), reasons=reasons,
        eligible_for_manual_review=safe,
        eligible_for_automatic_contact=safe and candidate.contact_basis.allows_automatic_first_contact,
    )


def prepare_partner_proposal(
    *, partner: Partner, candidate: PartnerOpportunity,
    business_name: str, offering: str,
    campaign_topic: str, target_url: str,
) -> PartnerPreparedProposal:
    """Produces only a factual *draft*, never a queued provider send."""
    if (partner.status is not PartnerStatus.ACTIVE
            or partner.partner_id != candidate.partner_id
            or partner.business_id != candidate.business_id
            or candidate.competitor):
        raise PermissionError("partner_proposal_unavailable")
    url = urlsplit(target_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("partner_public_link_invalid")
    values = (business_name, offering, campaign_topic)
    if any(not v or len(v) > 240 or any(ord(c) < 32 for c in v) for v in values):
        raise ValueError("partner_proposal_fields_invalid")
    summary = f"{business_name}: {offering}."
    outreach = (
        f"Здравствуйте! Предлагаем рассмотреть совместный материал на тему «{campaign_topic}». "
        f"Мы подготовим содержание от имени {business_name}. "
        "Публикация возможна только по вашему согласованию."
    )
    joint = f"{campaign_topic}\n\n{summary}\n\nПодробнее: {target_url}"
    return PartnerPreparedProposal(
        partner_id=partner.partner_id, business_id=partner.business_id,
        outreach_draft=outreach, joint_content_draft=joint,
    )
