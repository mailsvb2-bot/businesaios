from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.newsletter_intelligence_family import NewsletterIntelligenceFamilyConnector


@dataclass
class SubstackNewslettersConnector(NewsletterIntelligenceFamilyConnector):
    connector_name: str = 'substack_newsletters'
    connector_id: str = 'substack_newsletters'
    provider_key: str = 'substack'
    version: str = 'v1'


__all__ = ['SubstackNewslettersConnector']
