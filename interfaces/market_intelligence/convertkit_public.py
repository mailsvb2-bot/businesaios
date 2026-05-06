from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.newsletter_intelligence_family import NewsletterIntelligenceFamilyConnector


@dataclass
class ConvertkitPublicConnector(NewsletterIntelligenceFamilyConnector):
    connector_name: str = 'convertkit_public'
    connector_id: str = 'convertkit_public'
    provider_key: str = 'convertkit'
    version: str = 'v1'


__all__ = ['ConvertkitPublicConnector']
