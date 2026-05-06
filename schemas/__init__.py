from __future__ import annotations

"""Canonical validation and serialization schema surface."""

from schemas.helpers import required_fields_schema, validate_required_fields
from typing import Mapping

CANON_SCHEMA_NAMESPACE = True

BUSINESS_LIVE_STATE_SCHEMA = required_fields_schema('business_id', 'open_now', 'capacity_score', 'quality_score', 'risk_score')
CLIENT_INTENT_SCHEMA = required_fields_schema('service_type', 'urgency', 'budget_band', 'quality_band', 'confidence')
DELIVERY_OUTCOME_SCHEMA = required_fields_schema('request_id', 'business_id', 'delivery_status', 'channel')
LEAD_DELIVERY_SCHEMA = required_fields_schema('request_id', 'business_id', 'delivery_status', 'channel')
MARKET_HEALTH_SCHEMA = required_fields_schema('utilization_ratio', 'concentration_ratio', 'overflow_ratio')
MATCH_CANDIDATE_SCHEMA = required_fields_schema('business_id', 'score', 'score_breakdown', 'reasons', 'blocked')
ROUTING_DECISION_SCHEMA = required_fields_schema('request_id', 'selected_business_id', 'trace', 'requires_manual_review')

_ACTION_REQUIRED_FIELDS = ('action_id', 'action_type', 'channel')
_BUSINESS_PROFILE_REQUIRED_FIELDS = ('business_id', 'goal', 'region')
_CAMPAIGN_REQUIRED_FIELDS = ('campaign_id', 'channel', 'budget')
_FEEDBACK_REQUIRED_FIELDS = ('feedback_id', 'kind', 'value')
_LEAD_REQUIRED_FIELDS = ('lead_id', 'status', 'source')
_MARKETPLACE_MATCH_REQUIRED_FIELDS = ('match_id', 'business_id', 'client_id')
_OPPORTUNITY_REQUIRED_FIELDS = ('opportunity_id', 'kind', 'score')
_PLATFORM_LISTING_REQUIRED_FIELDS = ('listing_id', 'platform', 'status')
_REVENUE_REQUIRED_FIELDS = ('snapshot_id', 'revenue')

def validate_action(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _ACTION_REQUIRED_FIELDS)

def validate_business_profile(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _BUSINESS_PROFILE_REQUIRED_FIELDS)

def validate_campaign(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _CAMPAIGN_REQUIRED_FIELDS)

def validate_feedback(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _FEEDBACK_REQUIRED_FIELDS)

def validate_lead(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _LEAD_REQUIRED_FIELDS)

def validate_marketplace_match(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _MARKETPLACE_MATCH_REQUIRED_FIELDS)

def validate_opportunity(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _OPPORTUNITY_REQUIRED_FIELDS)

def validate_platform_listing(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _PLATFORM_LISTING_REQUIRED_FIELDS)

def validate_revenue(document: Mapping[str, object]) -> list[str]:
    return validate_required_fields(document, _REVENUE_REQUIRED_FIELDS)

_SCHEMA_EXPORTS = {
    'action_schema': {'validate': 'schemas:validate_action', 'REQUIRED_FIELDS': 'schemas:_ACTION_REQUIRED_FIELDS'},
    'business_profile_schema': {'validate': 'schemas:validate_business_profile', 'REQUIRED_FIELDS': 'schemas:_BUSINESS_PROFILE_REQUIRED_FIELDS'},
    'campaign_schema': {'validate': 'schemas:validate_campaign', 'REQUIRED_FIELDS': 'schemas:_CAMPAIGN_REQUIRED_FIELDS'},
    'feedback_schema': {'validate': 'schemas:validate_feedback', 'REQUIRED_FIELDS': 'schemas:_FEEDBACK_REQUIRED_FIELDS'},
    'lead_schema': {'validate': 'schemas:validate_lead', 'REQUIRED_FIELDS': 'schemas:_LEAD_REQUIRED_FIELDS'},
    'marketplace_match_schema': {'validate': 'schemas:validate_marketplace_match', 'REQUIRED_FIELDS': 'schemas:_MARKETPLACE_MATCH_REQUIRED_FIELDS'},
    'opportunity_schema': {'validate': 'schemas:validate_opportunity', 'REQUIRED_FIELDS': 'schemas:_OPPORTUNITY_REQUIRED_FIELDS'},
    'platform_listing_schema': {'validate': 'schemas:validate_platform_listing', 'REQUIRED_FIELDS': 'schemas:_PLATFORM_LISTING_REQUIRED_FIELDS'},
    'revenue_schema': {'validate': 'schemas:validate_revenue', 'REQUIRED_FIELDS': 'schemas:_REVENUE_REQUIRED_FIELDS'},
    'business_live_state_schema': {'BUSINESS_LIVE_STATE_SCHEMA': 'schemas:BUSINESS_LIVE_STATE_SCHEMA'},
    'client_intent_schema': {'CLIENT_INTENT_SCHEMA': 'schemas:CLIENT_INTENT_SCHEMA'},
    'delivery_outcome_schema': {'DELIVERY_OUTCOME_SCHEMA': 'schemas:DELIVERY_OUTCOME_SCHEMA'},
    'lead_delivery_schema': {'LEAD_DELIVERY_SCHEMA': 'schemas:LEAD_DELIVERY_SCHEMA'},
    'market_health_schema': {'MARKET_HEALTH_SCHEMA': 'schemas:MARKET_HEALTH_SCHEMA'},
    'match_candidate_schema': {'MATCH_CANDIDATE_SCHEMA': 'schemas:MATCH_CANDIDATE_SCHEMA'},
    'routing_decision_schema': {'ROUTING_DECISION_SCHEMA': 'schemas:ROUTING_DECISION_SCHEMA'},
}

__all__ = [
    'BUSINESS_LIVE_STATE_SCHEMA', 'CANON_SCHEMA_NAMESPACE', 'CLIENT_INTENT_SCHEMA', 'DELIVERY_OUTCOME_SCHEMA',
    'LEAD_DELIVERY_SCHEMA', 'MARKET_HEALTH_SCHEMA', 'MATCH_CANDIDATE_SCHEMA', 'ROUTING_DECISION_SCHEMA',
    'required_fields_schema', 'validate_action', 'validate_business_profile', 'validate_campaign', 'validate_feedback',
    'validate_lead', 'validate_marketplace_match', 'validate_opportunity', 'validate_platform_listing', 'validate_required_fields',
    'validate_revenue',
]
