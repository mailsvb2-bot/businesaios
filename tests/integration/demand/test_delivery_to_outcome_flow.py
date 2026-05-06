from __future__ import annotations

from lead_outcomes import LeadOutcomeRegistry
from lead_outcomes import LeadStatusTracker
from lead_outcomes import LeadConversionTracker
from lead_outcomes import LeadRevenueTracker

def test_delivery_to_outcome_flow():
    registry = LeadOutcomeRegistry()
    LeadStatusTracker().update(registry, "r1", "delivered")
    LeadConversionTracker().update(registry, "r1", True)
    LeadRevenueTracker().update(registry, "r1", 100.0)
    row = registry.get("r1")
    assert row["converted"] is True
    assert row["revenue"] == 100.0
