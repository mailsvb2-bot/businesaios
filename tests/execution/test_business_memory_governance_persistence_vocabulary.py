from execution.business_memory_governance import BusinessMemoryGovernanceGate


def test_governance_gate_reads_region_channel_from_persistence_vocabulary() -> None:
    gate = BusinessMemoryGovernanceGate(min_fit_score=0.30)
    report = gate.evaluate(
        candidate_record={
            'goal': 'increase revenue',
            'canonical_persistence_vocabulary': {
                'goal': 'increase revenue',
                'stop_reason': 'goal_reached',
                'region': 'eu',
                'channel': 'headless',
                'goal_score': 0.91,
                'retry_kind': 'success',
            },
            'final_feedback': {
                'goal_score': 0.91,
                'goal_reached': True,
                'retry_classification': {'kind': 'success'},
            },
        },
        business_memory_summary={
            'active_goals': ['increase revenue'],
            'learned_preferences': {'region': 'eu', 'channel': 'headless'},
            'recurring_failures': ['timeout'],
            'recurring_wins': ['goal_reached'],
        },
    )
    assert report.approved is True
    assert 'region_matches_preference' in report.reasons
    assert 'channel_matches_preference' in report.reasons
