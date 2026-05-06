from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.newsletter_intelligence_family import NewsletterIntelligenceFamilyConnector


@dataclass
class BeehiivConnector(NewsletterIntelligenceFamilyConnector):
    connector_name: str = 'beehiiv'
    connector_id: str = 'beehiiv'
    provider_key: str = 'beehiiv'
    version: str = 'v1'


__all__ = ['BeehiivConnector']
