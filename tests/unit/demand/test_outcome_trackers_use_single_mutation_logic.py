from lead_outcomes import LeadContactTracker
from lead_outcomes import LeadConversionTracker
from lead_outcomes import LeadOutcomeRegistry
from lead_outcomes import LeadRevenueTracker
from lead_outcomes import LeadStatusTracker


def test_trackers_accumulate_fields_without_overwriting_existing_row() -> None:
    registry = LeadOutcomeRegistry()
    LeadStatusTracker().update(registry, 'r1', 'queued')
    LeadContactTracker().update(registry, 'r1', True)
    LeadConversionTracker().update(registry, 'r1', False)
    LeadRevenueTracker().update(registry, 'r1', 0.0)

    row = registry.require('r1')
    assert row['status'] == 'queued'
    assert row['contacted'] is True
    assert row['converted'] is False
    assert row['revenue'] == 0.0
