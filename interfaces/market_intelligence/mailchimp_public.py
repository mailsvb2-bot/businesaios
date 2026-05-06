from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.newsletter_intelligence_family import NewsletterIntelligenceFamilyConnector


@dataclass
class MailchimpPublicConnector(NewsletterIntelligenceFamilyConnector):
    connector_name: str = 'mailchimp_public'
    connector_id: str = 'mailchimp_public'
    provider_key: str = 'mailchimp'
    version: str = 'v1'


__all__ = ['MailchimpPublicConnector']
