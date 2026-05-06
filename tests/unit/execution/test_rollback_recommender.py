from execution.rollback_recommender import MemoryAwareRollbackRecommender


def test_rollback_recommender_prefers_high_drift_and_known_failure() -> None:
    payload = MemoryAwareRollbackRecommender().recommend(
        candidate_record={'stop_reason': 'execution_failed', 'final_feedback': {'error': 'timeout'}},
        baseline_record={'source_run_id': 'run-0'},
        drift_payload={'severity': 'high'},
        business_memory_summary={'recurring_failures': ['timeout']},
        fallback_candidates=[{'run_id': 'run-2', 'completed': True, 'final_feedback': {'goal_score': 0.9}}],
    )
    assert payload.should_rollback is True
    assert payload.recommended_run_id == 'run-2'
