from lead_outcomes import LeadOutcomeRegistry, LeadRevenueTracker, LeadStatusTracker


def test_field_trackers_use_shared_mutation_path() -> None:
    registry = LeadOutcomeRegistry()
    LeadStatusTracker().update(registry, 'req-1', 'queued')
    LeadRevenueTracker().update(registry, 'req-1', 12)

    row = registry.require('req-1')
    assert row['status'] == 'queued'
    assert row['revenue'] == 12.0
