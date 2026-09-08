from __future__ import annotations

from core.analytics.business_scorecard import BusinessAnalyticsService


def test_business_scorecard_builds_core_metrics():
    service = BusinessAnalyticsService()
    events = [
        {'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1710000000000, 'payload': {'offer_id': 'o1'}},
        {'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 1710000001000, 'payload': {'offer_id': 'o1'}},
        {'event_type': 'purchase_attempt', 'user_id': 'u1', 'timestamp_ms': 1710000002000, 'payload': {'offer_id': 'o1'}},
        {'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 1710000003000, 'payload': {'offer_id': 'o1', 'amount': 100.0, 'amount_minor': 10000, 'currency': 'rub'}},
        {'event_type': 'offer_shown', 'user_id': 'u2', 'timestamp_ms': 1710086400000, 'payload': {'offer_id': 'o1'}},
        {'event_type': 'decision_issued', 'user_id': 'u1', 'timestamp_ms': 1710000001500, 'payload': {}},
        {'event_type': 'decision_executed', 'user_id': 'u1', 'timestamp_ms': 1710000002500, 'payload': {}},
        {'event_type': 'latency_span', 'user_id': 'u1', 'timestamp_ms': 1710000003500, 'payload': {'duration_ms': 800}},
        {'event_type': 'latency_span', 'user_id': 'u2', 'timestamp_ms': 1710086401000, 'payload': {'duration_ms': 1200}},
        {'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1710172800000, 'payload': {'offer_id': 'o1'}},
    ]
    scorecard = service.build_scorecard(tenant_id='tenant-a', events=events, window_days=30, generated_at_ms=1710200000000)
    assert scorecard.tenant_id == 'tenant-a'
    assert scorecard.traffic_users == 2
    assert scorecard.funnel.offer_shown == 2
    assert scorecard.funnel.offer_clicked == 1
    assert scorecard.revenue.revenue_total == 100.0
    assert scorecard.metadata['revenue_currency'] == 'RUB'
    assert scorecard.metadata['revenue_money_status'] == 'verified_minor_units'
    assert scorecard.metadata['revenue_minor_total'] == '10000'
    assert all(isinstance(value, str) for value in scorecard.metadata.values())
    assert scorecard.retention.returning_users == 1
    assert scorecard.decisions.execution_ratio == 1.0
    assert scorecard.latency.sample_count == 2


def test_business_scorecard_money_metadata_requires_strict_minor_units_and_one_currency():
    service = BusinessAnalyticsService()
    mixed = service.build_scorecard(tenant_id='tenant-a', events=[
        {'event_type': 'purchase_success', 'user_id': 'u1', 'payload': {'amount_minor': 10000, 'currency': 'RUB'}},
        {'event_type': 'purchase_success', 'user_id': 'u2', 'payload': {'amount_minor': 200, 'currency': 'USD'}},
    ])
    legacy = service.build_scorecard(tenant_id='tenant-a', events=[
        {'event_type': 'purchase_success', 'user_id': 'u1', 'payload': {'amount': 100, 'currency': 'RUB'}},
    ])
    malformed = service.build_scorecard(tenant_id='tenant-a', events=[
        {'event_type': 'purchase_success', 'user_id': 'u1', 'payload': {'amount_minor': True, 'currency': 'RUB'}},
    ])
    assert mixed.metadata['revenue_money_status'] == 'mixed_currency' and mixed.metadata['revenue_minor_total'] == ''
    assert legacy.metadata['revenue_money_status'] == 'unverified' and legacy.metadata['revenue_minor_total'] == ''
    assert malformed.metadata['revenue_money_status'] == 'unverified' and malformed.metadata['revenue_minor_total'] == ''
