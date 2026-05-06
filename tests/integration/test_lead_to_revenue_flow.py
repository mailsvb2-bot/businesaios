from attribution.lead_to_revenue_resolver import LeadToRevenueResolver


def test_lead_to_revenue_flow_returns_payload():
    result = LeadToRevenueResolver().resolve({'lead_id': 'l1', 'revenue': 100})
    assert result['kind'] == 'lead_revenue_resolution'
