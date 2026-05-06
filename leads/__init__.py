"""Lead package."""

from __future__ import annotations

from leads.lead_capture_facade import LeadCaptureFacade, LeadRouter
from shared.kinded_payloads import build_kinded_payload

class LeadDeduplication:
    def deduplicate(self, payload: dict) -> dict:
        return build_kinded_payload('lead_deduplication', payload)

class LeadIngestion:
    def ingest(self, payload: dict) -> dict:
        return build_kinded_payload('lead_ingestion', payload)

class LeadOwnerNotifications:
    def notify(self, payload: dict) -> dict:
        return build_kinded_payload('lead_owner_notification', payload)

class LeadQualityScorer:
    def score(self, payload: dict) -> dict:
        return build_kinded_payload('lead_quality_score', payload)

class LeadRegistry:
    def register(self, payload: dict) -> dict:
        return build_kinded_payload('lead_registry', payload)

class LeadSourceMapper:
    def map(self, payload: dict) -> dict:
        return build_kinded_payload('lead_source_map', payload)

class LeadStatusUpdater:
    def update(self, payload: dict) -> dict:
        return build_kinded_payload('lead_status_update', payload)

class LeadTimeline:
    def append(self, payload: dict) -> dict:
        return build_kinded_payload('lead_timeline', payload)

__all__ = [
    'LeadCaptureFacade',
    'LeadDeduplication',
    'LeadIngestion',
    'LeadOwnerNotifications',
    'LeadQualityScorer',
    'LeadRegistry',
    'LeadRouter',
    'LeadSourceMapper',
    'LeadStatusUpdater',
    'LeadTimeline',
]
