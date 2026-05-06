from __future__ import annotations

from demand_capture.sources._base import StaticOriginIngestor

CANON_DEMAND_CAPTURE_SOURCES_ALIAS_NAMESPACE = True
CANON_DEMAND_CAPTURE_SOURCES_PACKAGE_OWNER = True

class AvitoInquiryIngestor(StaticOriginIngestor):
    ORIGIN = "avito_inquiry"

class CallTrackingIngestor(StaticOriginIngestor):
    ORIGIN = "call_tracking"

class EmailLeadIngestor(StaticOriginIngestor):
    ORIGIN = "email_lead"

class GoogleMapsInquiryIngestor(StaticOriginIngestor):
    ORIGIN = "google_maps_inquiry"

class MarketplaceOrderIntentIngestor(StaticOriginIngestor):
    ORIGIN = "marketplace_order_intent"

class OlxInquiryIngestor(StaticOriginIngestor):
    ORIGIN = "olx_inquiry"

class TelegramIngestor(StaticOriginIngestor):
    ORIGIN = "telegram"

class WebsiteFormIngestor(StaticOriginIngestor):
    ORIGIN = "website_form"

class WhatsappIngestor(StaticOriginIngestor):
    ORIGIN = "whatsapp"

class YandexMapsInquiryIngestor(StaticOriginIngestor):
    ORIGIN = "yandex_maps_inquiry"

class YelpInquiryIngestor(StaticOriginIngestor):
    ORIGIN = "yelp"

__all__ = [
    "CANON_DEMAND_CAPTURE_SOURCES_ALIAS_NAMESPACE",
    "CANON_DEMAND_CAPTURE_SOURCES_PACKAGE_OWNER",
    "AvitoInquiryIngestor",
    "CallTrackingIngestor",
    "EmailLeadIngestor",
    "GoogleMapsInquiryIngestor",
    "MarketplaceOrderIntentIngestor",
    "OlxInquiryIngestor",
    "TelegramIngestor",
    "WebsiteFormIngestor",
    "WhatsappIngestor",
    "YandexMapsInquiryIngestor",
    "YelpInquiryIngestor",
]
