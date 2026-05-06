from execution.canonical_governance_decision import (
    canonical_baseline_selection_decision,
    canonical_promotion_decision,
    canonical_rollback_recommendation_decision,
)


def test_canonical_baseline_selection_decision_keeps_ranked_candidates() -> None:
    payload = canonical_baseline_selection_decision(
        baseline_name='baseline-1',
        selected_record={'run_id': 'run-1', 'goal': 'grow'},
        ranked_candidates=[{'run_id': 'run-1', 'goal_score': 0.91, 'rank': 1}],
        promotion_decision={'approved': True, 'reason': 'approved'},
    )
    decision = payload['governance_decision']
    assert decision['decision_type'] == 'select_baseline'
    assert decision['selected_run_id'] == 'run-1'
    assert decision['ranked_candidates'][0]['run_id'] == 'run-1'


def test_canonical_promotion_decision_embeds_fit_report() -> None:
    payload = canonical_promotion_decision(
        baseline_name='baseline-1',
        candidate_record={'run_id': 'run-1', 'final_feedback': {'goal_score': 0.88}},
        label='manual',
        fit_report={'approved': True, 'score': 0.62, 'reasons': ['candidate_goal_reached']},
    )
    decision = payload['governance_decision']
    assert decision['decision_type'] == 'promote_baseline'
    assert decision['fit_report']['approved'] is True
    assert decision['metadata']['label'] == 'manual'


def test_canonical_rollback_recommendation_decision_uses_recommended_run() -> None:
    payload = canonical_rollback_recommendation_decision(
        baseline_name='baseline-1',
        candidate_run_id='run-2',
        recommendation={
            'should_rollback': True,
            'confidence': 0.82,
            'reason': 'high_drift',
            'recommended_run_id': 'run-1',
        },
    )
    decision = payload['governance_decision']
    assert decision['decision_type'] == 'rollback_recommendation'
    assert decision['approved'] is True
    assert decision['selected_run_id'] == 'run-1'
